import ssl
import sys
from functools import partial
from typing import Annotated, TypedDict, List, Optional
import psycopg
from psycopg.rows import dict_row
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from kuking.config import settings
from kuking.schemas import IntentSchema, ExpensePayload
from kuking.prompts import ROUTER_SYSTEM_PROMPT, RECIPE_SYSTEM_PROMPT
from kuking.db import get_user_pantry, save_expenses_and_pantry, get_ssl_context
import asyncpg

# State definition
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    telegram_user_id: int
    intent: Optional[str]

# LLM Clients
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.2
)

router_chain = llm.with_structured_output(IntentSchema)
expense_chain = llm.with_structured_output(ExpensePayload)

# Node 1: Intent Routing
async def router_node(state: AgentState) -> dict:
    last_msg = state["messages"][-1].content
    result: IntentSchema = await router_chain.ainvoke([
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=last_msg)
    ])
    return {"intent": result.intent}

# Node 2: Recipe Generation 
async def recipe_node(state: AgentState, pool: asyncpg.Pool) -> dict:
    user_id = state["telegram_user_id"]
    last_msg = state["messages"][-1].content
    
    # kulkas dari db
    pantry = await get_user_pantry(pool, user_id)
    pantry_info = ", ".join(pantry) if pantry else "Belum ada bahan tercatat di kulkas."
    
    context_prompt = (
        f"Konteks isi kulkas pengguna saat ini: [{pantry_info}]\n"
        f"Pesan pengguna: {last_msg}"
    )
    
    response = await llm.ainvoke([
        SystemMessage(content=RECIPE_SYSTEM_PROMPT),
        HumanMessage(content=context_prompt)
    ])
    return {"messages": [response]}

# Node 3: Expense Logging & Inventory Sync
async def expense_node(state: AgentState, pool: asyncpg.Pool) -> dict:
    user_id = state["telegram_user_id"]
    last_msg = state["messages"][-1].content
    
    extraction: ExpensePayload = await expense_chain.ainvoke([
        SystemMessage(content="Ekstraksi seluruh item belanja dan konversi angka ke nominal integer."),
        HumanMessage(content=last_msg)
    ])
    
    if not extraction.items:
        return {"messages": [AIMessage(content="Saya tidak menemukan item belanja atau nominal harga yang jelas pada pesan tersebut.")]}
    
    # save
    added_pantry = await save_expenses_and_pantry(pool, user_id, extraction.items)
    
    # Format respon konfirmasi
    lines = [f"• {i.item_name} ({i.quantity_note or '-'}): Rp {i.amount_idr:,}" for i in extraction.items]
    output = (
        f"*Catatan Belanja Berhasil Disimpan*\n\n"
        + "\n".join(lines) + "\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Total:* Rp {extraction.grand_total:,}\n"
    )
    if added_pantry:
        output += f"\n🧊 *Masuk inventaris kulkas:* {', '.join(added_pantry)}"
        
    return {"messages": [AIMessage(content=output)]}

# Node 4: View Pantry
async def pantry_view_node(state: AgentState, pool: asyncpg.Pool) -> dict:
    user_id = state["telegram_user_id"]
    pantry = await get_user_pantry(pool, user_id)
    
    if not pantry:
        msg = "Kulkas Anda masih kosong. Bahan akan otomatis tersimpan saat Anda mencatat belanjaan pangan."
    else:
        items = "\n".join([f"• {item.title()}" for item in pantry])
        msg = f"*Daftar Bahan di Kulkas Anda:*\n\n{items}\n\nIngin saya buatkan resep dari bahan-bahan ini?"
        
    return {"messages": [AIMessage(content=msg)]}

# Node 5: General Node
async def general_node(state: AgentState) -> dict:
    return {"messages": [AIMessage(content="Halo! Saya asisten dapur Anda. Anda bisa mencatat belanjaan (misal: 'Beli ayam 25rb sama sawi 5rb') atau menanyakan ide resep masakan.")]}

# Routing Condition
def route_decision(state: AgentState) -> str:
    intent = state.get("intent")
    mapping = {
        "RECIPE_QUERY": "recipe",
        "EXPENSE_LOG": "expense",
        "PANTRY_VIEW": "pantry",
        "GENERAL": "general"
    }
    return mapping.get(intent, "general")

# Graph Builder
async def create_cooking_agent(pool: asyncpg.Pool):
    clean_url = settings.SUPABASE_DB_URL.split("?")[0]
    
    # Inisialisasi checkpointer 
    checkpointer_conn = await psycopg.AsyncConnection.connect(
        clean_url,
        autocommit=True,
        row_factory=dict_row
    )
    checkpointer = AsyncPostgresSaver(checkpointer_conn)
    await checkpointer.setup()  
    
    workflow = StateGraph(AgentState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("recipe", partial(recipe_node, pool=pool))
    workflow.add_node("expense", partial(expense_node, pool=pool))
    workflow.add_node("pantry", partial(pantry_view_node, pool=pool))
    workflow.add_node("general", general_node)
    
    workflow.set_entry_point("router")
    
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "recipe": "recipe",
            "expense": "expense",
            "pantry": "pantry",
            "general": "general"
        }
    )
    
    workflow.add_edge("recipe", END)
    workflow.add_edge("expense", END)
    workflow.add_edge("pantry", END)
    workflow.add_edge("general", END)
    
    return workflow.compile(checkpointer=checkpointer), checkpointer_conn