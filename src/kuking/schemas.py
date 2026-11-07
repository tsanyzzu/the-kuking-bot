from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class IntentSchema(BaseModel):
    intent: Literal["RECIPE_QUERY", "EXPENSE_LOG", "PANTRY_VIEW", "GENERAL"] = Field(
        description="Klasifikasi intensi input user."
    )

class ExpenseItem(BaseModel):
    item_name: str = Field(description="Nama bahan mentah atau kebutuhan dapur dalam bentuk baku, misal: 'Daging Sapi', 'Bawang Merah'")
    category: Literal["Protein", "Sayur/Bumbu", "Sembako", "Lainnya"] = Field(
        description="Kategori item dapur."
    )
    quantity_note: Optional[str] = Field(
        default=None, 
        description="Satuan/jumlah jika terdeteksi (misal: '500 gram', '2 ikat', '1 botol')"
    )
    amount_idr: int = Field(description="Harga total item dalam angka Rupiah tanpa simbol (integer)")
    is_pantry_item: bool = Field(
        description="True jika item merupakan bahan masakan/pangan yang bisa disimpan di dapur untuk dimasak."
    )

class ExpensePayload(BaseModel):
    items: List[ExpenseItem] = Field(description="Daftar seluruh item belanja yang terdeteksi.")
    grand_total: int = Field(description="Total pengeluaran riil hasil penjumlahan seluruh item.")