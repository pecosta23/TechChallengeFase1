from fastapi import FastAPI
from app.routers import vitibrasil
from app.core import init_db
import uvicorn
import logging
import nest_asyncio

nest_asyncio.apply()

app = FastAPI(
    title="Vitibrasil API",
    version ="1.0.0"
    )

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message).200s",
    datefmt='%d/%m/%Y %I:%M:%S %p',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app/logs/.logs")
    ]
)

app.include_router(vitibrasil.router)

async def main():
    await init_db()
    uvicorn.run(app, host='127.0.0.1', port=5000)
    # uvicorn app.main:app --reload
        # para testar a api precisa ativar com o comando acima
    
if __name__ == "__main__":
    main()
