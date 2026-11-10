import os
import sys
import gradio as gr
from kuking.main import app as fastapi_app

sys.path.insert(0, os.path.abspath("src"))

with gr.Blocks(title="Kuking status") as demo:
    gr.Markdown("## Kuking")
    gr.Markdown("Asal bisa masak")

app = gr.mount_gradio_app(fastapi_app, demo, path="/")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)