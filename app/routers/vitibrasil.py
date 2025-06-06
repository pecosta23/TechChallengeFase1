from fastapi import APIRouter, Query, Depends, HTTPException, Form, Body
from typing import Optional
import sqlite3
from app.util.auth import verifica_token, cria_token, hash_pass, verifica_pass, oauth2
from app.core.database_config import init_db
from app.core.logging_config import logging_config
import logging
from pydantic import BaseModel
from app.services.scraper_producao import get_producao
from app.services.scraper_processamento import get_processamento
from app.services.scraper_comercializacao import get_comercializacao
from app.services.scraper_importacao import get_importacao
from app.services.scraper_exportacao import get_exportacao
from fastapi.responses import JSONResponse, RedirectResponse


router = APIRouter()
logging_config()
class UserRequest(BaseModel):
    username: str
    password: str

@router.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@router.post(
    "/signup", tags=["Usuários"],
    responses={
        200: {
            "description": "Usuário cadastrado com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Usuário cadastrado com sucesso!"
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos dados.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "username"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def sign_up(user: UserRequest = Body(
        ...,
        example={
            "username": "usuario",
            "password": "senha"
        }
    )
) -> dict:
    """
        ### Descrição:
            Rota de cadastro de usuários.
       ### Parâmetros:
            - method: POST
            - headers: content-type: application/json
            - Body JSON:
                {
                    "username": "usuario",
                    "password": "senha"
                }
        ### Retorno:
            Retorna uma mensagem de confirmação de que o usuário foi cadastrado com sucesso.
    """
    await init_db()
    logging.info('Iniciando sign-up')
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    hashed_pw = hash_pass(user.password)

    try:
        cursor.execute('''
            INSERT INTO users (username, password) VALUES (?, ?)
        ''', (user.username, hashed_pw))
        conn.commit()
        logging.info(f"Usuário {user.username} cadastrado com sucesso.")
        return JSONResponse(status_code=200,content={"message": "Usuário cadastrado com sucesso!"})
    except sqlite3.IntegrityError:
        logging.error(f"Usuário {user.username} já existe.")
        raise HTTPException(status_code=202, detail="Usuário já existe.")
    finally:
        conn.close()

@router.post(
    "/login", tags=["Usuários"],
    responses={
        200: {
            "description": "Token de acesso gerado com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "bearer"
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos dados.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "username"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def login_user (
    username: str = Form(...),
    password: str = Form(...)
) -> dict:
    """
        ### Descrição:
            Esta rota é responsável por autenticar o usuário e retornar um token de acesso.
       ### Parâmetros:
            - headers: content-type: application/json
            - method: POST
            - Body JSON:
                {
                    "username": "usuario",
                    "password": "senha"
                }
        ### Retorno:
            Retorna o token de acesso se as credenciais forem válidas.
    """

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()

    if not result or not verifica_pass(password, result[0]):
        raise HTTPException(status_code=401, detail="As credenciais são inválidas")

    access_token = cria_token(data={"sub": username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get(
    "/producao/options", tags=["Vitivinicultura"],
    responses={
        200: {
            "description": "Opções de produção retornadas com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "categories": ["vinho de mesa","vinho fino de mesa (vinifera)","suco","derivados"],
                        "products": ["Todos da categoria","tinto","branco","rosado"]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def producao_opcoes() -> dict:
    """
        ### Descrição:
            Rota para obter as opções de categorias e produtos disponíveis na produção.
       ### Parâmetros:
            - headers: content-type: application/json
            - method: GET
        ### Retorno:
            Retorna uma lista de categorias e produtos disponíveis.
    """
    try:
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Category FROM producao")
        categories = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT Product FROM producao")
        products = [row[0] for row in cursor.fetchall()]
        conn.close()
        return JSONResponse(status_code=200, content={"success": True, "categories": categories, "products": products})
    except Exception as e:
        logging.error(f"Erro ao acessar o banco de dados: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)}) 

@router.get(
    "/producao", tags=["Vitivinicultura"],
    responses={
        200: {
            "description": "Dados de produção retornados com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "total": 1,
                        "data": [
                            {
                                "Year": 2020,
                                "Category": "vinho de mesa",
                                "Product": "tinto",
                                "Quantity_L": "175.267.437"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def producao (
    year: int = Query(None, ge=1970, le=2023),
    category: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    token_user: str = Depends(verifica_token)
) -> dict:
    """
        ### Descrição:
            Rota de Produção.
       ### Parâmetros:
            - headers:
                - Authorization: Bearer {token}
            - method: GET
            - parameters:
                - year: int (obrigatório, ano de 1970 a 2023)
                - category: str (opcional, categoria do produto)
                - product: str (opcional, nome do produto)
        ### Retorno:
            Retorna dados de produção filtrados por ano, produto e categoria.
        ### Exemplo de uso:
            curl -X 'GET' 
                '/producao?year=2001&product=Tinto&category=Vinho%20de%20mesa' 
                -H 'accept: application/json' 
                -H 'Authorization: Bearer TOKEN_EXAMPLE'
            Retorna dados de produção de Tinto para o ano de 2001 na categoria Vinho de mesa.
    """
    try:
        df = get_producao(year)
        data = df.to_dict(orient="records")
        logging.info("Dados do site coletados com sucesso")
        filtered_data = data
        
        if product:
            filtered_data = [row for row in filtered_data if row.get("Product") and product.lower() in row["Product"].lower()]
        if category:
            filtered_data = [row for row in filtered_data if row.get("Category") and category.lower() in row["Category"].lower()]
        return JSONResponse(status_code=200, content={"success": True, "total": len(filtered_data), "data": filtered_data})
    except Exception as e:
        logging.error(f"Erro ao capturar dados do banco: {e}")
        return JSONResponse(status_code=500, content={"Success": False, "error": str(e)})
    except:
        logging.info("Erro ao capturar dados do site, tentando coletar do banco")
        conn = sqlite3.connect("vitibrasil.db") 
        cursor = conn.cursor()

        if year and product:
            logging.info(f"Capturando dados do banco para o ano {year} e produto {product}")
            query = "SELECT Year, Product, Quantity_L FROM producao WHERE Year = ? AND Product LIKE ?"
            cursor.execute(query, (year, product))

        else:
            query = "SELECT Year, Product, Quantity_L FROM producao WHERE Year = ?"
            cursor.execute(query,(year,))

        rows = cursor.fetchall()

        if not rows:
            logging.warning("Consulta ao banco realizada, mas nenhum dado encontrado.")
            conn.close()
            return JSONResponse(status_code=200, content={"success": True, "total": 0, "data": [], "message": "Nenhum dado encontrado no banco para os filtros informados."})

        data = [{"Year": row[0], "Product": row[1], "Quantity_L": row[2]} for row in rows]
        conn.close()
        return JSONResponse(status_code=200, content={"success": True, "total": len(data), "data": data})

@router.get(
    "/processamento/options", tags=["Vitivinicultura"],
    responses={
        200: {
            "description": "Opções de processamento retornadas com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "Grupo": ["tintas","brancas e rosadas","brancas","sem classificação"],
                        "Produtos": ["viníferas","americanas e híbridas","uvas de mesa","sem classificação"],
                        "Cultivos": ["tintas","alicante bouschet","ancelota"]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def processamento_opcoes() -> dict:
    """
        ### Descrição:
            Rota para obter as opções grupo, produtos e cultivos disponíveis na em processamento.
       ### Parâmetros:
            - headers: content-type: application/json
            - method: GET
        ### Retorno:
            Retorna uma lista de grupos, produtos e cultivos disponíveis.
    """
    try:
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT GroupName FROM processamento")
        group_name = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT Product FROM processamento")
        products = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT Cultive FROM processamento")
        cultives = [row[0] for row in cursor.fetchall()]
        conn.close()
        return JSONResponse(status_code=200, content={"success": True, "Grupo": group_name, "Produtos": products, "Cultivos": cultives})
    except Exception as e:
        logging.error(f"Erro ao acessar o banco de dados: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.get("/processamento",  tags=["Vitivinicultura"], responses={
        200: {
            "description": "Dados de processamento retornados com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "total": 1,
                        "data": [
                            {
                                "Year": 2020,
                                "GroupName": "Uva",
                                "Cultive": "Vinho",
                                "Quantity_Kg": 123456,
                                "Product": "Viníferas"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    })
async def processamento (
    product: str = Query(None),
    year: int = Query(None, ge=1970, le=2023),
    group:  Optional[str] = Query(None),
    cultive:  Optional[str] = Query(None),
    token_user: str = Depends(verifica_token))  -> dict:
    """
        ### Descrição:
            Rota de Processamento.
       ### Parâmetros:
            - headers:
                - Authorization: Bearer {token}
            - method: GET
            - parameters:
                - year: int (obrigatório, ano de 1970 a 2023)
                - product: str (obrigatório, nome do produto)
                - cultive: str (opcional, cultivo do produto)
        ### Retorno:
            Retorna dados de processamento filtrados por ano, produto e cultivo.
        ### Exemplo de uso:
            curl -X 'GET' 
                '/processamento?product=vin%C3%ADferas&year=2003&group=tintas&cultive=alfrocheiro' 
                -H 'accept: application/json' 
                -H 'Authorization: Bearer TOKEN_EXAMPLE'
            Retorna dados de processamento de Viníferas do grupo Tintas e cultivo Alfrocheiro, para o ano de 2003.
    """
    if product is None:
        return JSONResponse(status_code=400, content={"success": False, "error": "Necessário informar o produto: Viníferas, Uvas de mesa, Americanas e Híbridas ou Sem Classificação"})
    
    if product.lower() == 'viníferas' or product.lower() == 'viniferas':
        option = 1
    elif product.lower() == 'americanas e híbridas' or product.lower() == 'americanas e hibridas':
        option = 2
    elif product.lower() == 'uvas de mesa':
        option = 3
    elif product.lower() == 'sem classificação' or product.lower() == 'sem classificacao':
        option = 4
    else:
        return JSONResponse(status_code=400, content={"success": False, "error": "Produto inválido. Opções válidas: Viníferas, Uvas de mesa, Americanas e Híbridas ou Sem Classificação."})
    
    try:
        df = get_processamento(year, option)
   
        if group:
            df = df[df["GroupName"].str.contains(group, case=False, na=False)]
        if cultive:
            df = df[df["Cultive"].str.contains(cultive, case=False, na=False)]
        if product:
            df = df[df["Product"].str.contains(product, case=False, na=False)]
        data = df.to_dict(orient="records")
        logging.info("Dados do site coletados com sucesso")
        return JSONResponse(status_code=200, content={"success": True, "total": len(data), "data": data})
    except Exception as e:
        logging.error(f"Erro ao capturar dados do banco: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    except:
        logging.error("Erro ao capturar dados do site, tentando coletar do banco")

        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()

        query = "SELECT Year, GroupName, Cultive, Quantity_Kg, Product FROM processamento WHERE 1=1" 
        params = [] 

        if year is not None:
            query += " AND Year = ?"
            params.append(year) 

        if group:
            query += " AND GroupName LIKE ?"
            params.append(f"%{group}%")

        if cultive:
            query += " AND Cultive LIKE ?"
            params.append(f"%{cultive}%")
            
        if product:
            query += " AND Product LIKE ?"
            params.append(f"%{product}%")

        if year is not None:
            query += " AND Year = ?"
            params.append(year) 
        
        logging.info("QUERY:", query)
        logging.info("PARAMS:", params)
        cursor.execute(query, params) 
        rows = cursor.fetchall() 

        data = [{"Year": row[0], "GroupName": row[1], "Cultive": row[2], "Quantity_Kg": row[3]} for row in rows]
        conn.close() 
        
        return JSONResponse(status_code=200, content={"success": True, "total": len(data), "data": data})
    
@router.get(
    "/comercializacao/options", tags=["Vitivinicultura"],
    responses={
        200: {
            "description": "Opções de comercialização retornadas com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                         "Grupos": ["vinho de mesa","vinho fino de mesa","vinho frizante","vinho orgânico","vinho especial","espumantes","suco de uvas","suco de uvas concentrado","outros produtos comercializados"],"Cultivos": ["vinho de mesa","tinto","rosado","branco"]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def comercializacao_opcoes() -> dict:
    """
        ### Descrição:
            Rota para obter as opções de grupos e produtos disponíveis na comercialização.
       ### Parâmetros:
            - headers: content-type: application/json
            - method: GET
        ### Retorno:
            Retorna uma lista de grupos e produtos disponíveis.
    """
    try:
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT GroupName FROM comercializacao")
        group_name = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT Product FROM comercializacao")
        products = [row[0] for row in cursor.fetchall()]
        conn.close()
        return JSONResponse(status_code=200, content={"success": True, "Grupos": group_name, "Produtos": products})
    except Exception as e:
        logging.error(f"Erro ao acessar o banco de dados: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.get("/comercializacao", tags=["Vitivinicultura"], responses={
        200: {
            "description": "Dados de comercialização retornados com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "total": 1,
                        "data": [
                            {
                                "Year": 2020,
                                "GroupName": "Uva",
                                "Cultive": "Vinho",
                                "Quantity": 123456
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    })
async def comercializacao (
    year: int = Query(None, ge=1970, le=2023),
    group: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    token_user: str = Depends(verifica_token))  -> dict:
    """
        ### Descrição:
            Rota de Comercialização.
       ### Parâmetros:
            - headers:
                - Authorization: Bearer {token}
            - method: GET
            - parameters:
                - year: int (obrigatório, ano de 1970 a 2023)
                - group: str (opcional, nome do grupo)
                - cultive: str (opcional, cultivo do produto)
        ### Retorno:
            Retorna dados de produção em JSON filtrados por ano, grupo e cultivo. 
        ### Exemplo de uso:
            curl -X 'GET' 
                'comercializacao/?year=2002&group=VINHO%20FINO%20DE%20MESA&cultive=Tinto' 
                -H 'accept: application/json' 
                -H 'Authorization: Bearer TOKEN_EXAMPLE'
            Retorna dados de comercialização de VINHO FINO DE MESA para o ano de 2002 e cultivo Tinto.
    """
    try:
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()

        query = "SELECT Year, GroupName, Product, Quantity_L FROM comercializacao WHERE 1=1" 
        params = []

        if year is not None:
            query += " AND Year = ?"
            params.append(year)
        
        if group:
            query += " AND GroupName LIKE ?"
            params.append(group)

        if product:
            query += " AND Product LIKE ?"
            params.append(product)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        data = [{"Year": row[0], "GroupName": row[1], "Product": row[2], "Quantity": row[3]} for row in rows]
        conn.close()

        return JSONResponse(content={"success": True, "total": len(data), "data": data})
    
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})

@router.get(
    "/importacao/options", tags=["Vitivinicultura"],
    responses={
        200: {
            "description": "Opções de importação retornadas com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "Países": ["Africa do Sul","Alemanha","Argélia"]                
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def importacao_opcoes() -> dict:
    """
        ### Descrição:
            Rota para obter as opções de categorias e produtos disponíveis na importação.
       ### Parâmetros:
            - headers: content-type: application/json
            - method: GET
        ### Retorno:
            Retorna uma lista de países disponíveis.
    """
    try:
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Country FROM importacao")
        country = [row[0] for row in cursor.fetchall()]
        conn.close()
        return JSONResponse(status_code=200, content={"success": True, "Países": country})
    except Exception as e:
        logging.error(f"Erro ao acessar o banco de dados: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)}) 
    
@router.get("/importacao", tags=["Vitivinicultura"], responses={
        200: {
            "description": "Dados de importação retornados com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "total": 1,
                        "data": [
                            {
                                "Year": 2020,
                                "Country": "França",
                                "Quantity_Kg": 123456,
                                "Value_USD": 1000000,
                                "Product": "Vinhos de mesa"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    })
async def importacao (
    year: int = Query(None, ge= 1970, le= 2024),
    country: Optional[str] = Query(None),
    product: str = Query(None),
    token_user: str = Depends(verifica_token))  -> dict:
    """
        ### Descrição:
            Rota de Importação.
       ### Parâmetros:
            - headers:
                - Authorization: Bearer {token}
            - method: GET
            - parameters:
                - year: int (obrigatório, ano de 1970 a 2023)
                - country: str (opcional, nome do país importador)
                - product: str (obrigatório, nome do produto)
        ### Retorno:
            Retorna dados de importação filtrados por ano, país e produto.
        ### Exemplo de uso:
            curl -X 'GET' 
                '/importacao?year=2002&country=argentina&product=Vinhos%20de%20mesa' 
                -H 'accept: application/json' 
                -H 'Authorization: Bearer TOKEN_EXAMPLE'
            Retorna dados de importação de Vinhos de mesa para o ano de 2002 da Argentina.
    """
    if product is None:
        return {"Necessário informar o produto": "Vinhos de mesa, Espumantes, Uvas frescas, Uvas passas ou Suco de uva"}

    if product == 'Vinhos de mesa' or product == 'vinhos de mesa':
        option = 1
    elif product == 'Espumantes' or product == 'espumantes':
        option = 2
    elif product == 'Uvas frescas' or product == 'uvas frescas':
        option = 3
    elif product == 'Uvas passas' or product == 'uvas passas':
        option = 4
    elif product == 'Suco de uva' or product == 'suco de uva':
        option = 5
    else:
        return JSONResponse(status_code=400, content={"success": False, "error": "Produto inválido. Opções válidas: Vinhos de mesa, Espumantes, Uvas frescas, Uvas passas ou Suco de uva."})

    try:
        df = get_importacao(year, option)
        data = df.to_dict(orient="records")
        logging.info("Dados do site coletados com sucesso")
        filtered_data = data
        if product:
            filtered_data = [row for row in filtered_data if row.get("Product") and product.lower() in row["Product"].lower()]
        if country:
            filtered_data = [row for row in filtered_data if row.get("Country") and country.lower() in row["Country"].lower()]
        return JSONResponse(status_code=200, content={"success": True, "total": len(filtered_data), "data": filtered_data})
    except Exception as e:
        logging.error(f"Erro ao capturar dados do banco: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    except:
        logging.error("Erro ao capturar dados do site, tentando coletar do banco")
    
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()

        query = "SELECT Year, Country, Quantity_Kg, Value_USD, Product FROM importacao WHERE 1=1"
        params = []

        if year is not None:
            query += " AND Year = ?"
            params.append(year)
        
        if country:
            query += " AND Country LIKE ?"
            params.append(country)
            
        if product:
            query += " AND Product LIKE ?"
            params.append(product)
        

        cursor.execute(query, params)
        rows = cursor.fetchall()

        data = [{"Year": row[0], "Country": row[1], "Quantity_Kg": row[2], "Value_USD": row[3], "Product": row[4]} for row in rows]
        conn.close()

        return JSONResponse(status_code=200, content={"success": True, "total": len(data), "data": data})

@router.get(
    "/exportacao/options", tags=["Vitivinicultura"],
    responses={
        200: {
            "description": "Opções de exportação retornadas com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "Países": ["Africa do Sul","Alemanha","Argélia"]                
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def exportacao_opcoes() -> dict:
    """
        ### Descrição:
            Rota para obter os países disponíveis na exportação.
       ### Parâmetros:
            - headers: content-type: application/json
            - method: GET
        ### Retorno:
            Retorna uma lista de países disponíveis.
    """
    try:
        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Country FROM exportacao")
        country = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT Product FROM exportacao")
        products = [row[0] for row in cursor.fetchall()]
        conn.close()
        return JSONResponse(status_code=200, content={"success": True, "Países": country, "Produtos": products})
    except Exception as e:
        logging.error(f"Erro ao acessar o banco de dados: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)}) 

@router.get("/exportacao", tags=["Vitivinicultura"], responses={
        200: {
            "description": "Dados de exportação retornados com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "total": 1,
                        "data": [
                            {
                                "Year": 2020,
                                "Country": "França",
                                "Quantity_Kg": 123456,
                                "Value_USD": 1000000,
                                "Product": "vinho de mesa"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Erro de validação dos parâmetros.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "year"],
                                "msg": "value is not a valid integer",
                                "type": "type_error.integer"
                            }
                        ]
                    }
                }
            }
        }
    })
async def exportacao (
    year: int = Query(None, ge= 1970, le= 2024),
    product: str = Query(None),
    country: Optional[str] = Query(None),
    token_user: str = Depends(verifica_token))  -> dict:
    """
        ### Descrição:
            Rota de Exportação.
       ### Parâmetros:
            - headers:
                - Authorization: Bearer {token}
            - method: GET
            - parameters:
                - year: int (obrigatório, ano de 1970 a 2023)
                - country: str (opcional, nome do país exportador)
                - product: str (obrigatório, nome do produto)
        ### Retorno:
            Retorna dados de exportação filtrados por ano, país e produto.
        ### Exemplo de uso:
            curl -X 'GET' 
            '/exportacao?year=2010&product=Vinhos%20de%20mesa&country=Alemanha' 
            -H 'accept: application/json' 
            -H 'Authorization: Bearer TOKEN_EXAMPLE'
            Retorna dados de exportação de Vinhos de mesa para o ano de 2010 da Alemanha.
    """
    if product is None:
        return {"Necessário informar o produto": "Vinhos de mesa, Espumantes, Uvas frescas ou Suco de uva"}

    if product == 'Vinhos de mesa' or product == 'vinhos de mesa':
        option = 1
    elif product == 'Espumantes' or product == 'espumantes':
        option = 2
    elif product == 'Uvas frescas' or product == 'uvas frescas':
        option = 3
    elif product == 'Suco de uva' or product == 'suco de uva':
        option = 4
    else:
        return JSONResponse(status_code=400, content={"success": False, "error": "Produto inválido. Opções válidas: Vinhos de mesa, Espumantes, Uvas frescas, Uvas passas ou Suco de uva."})

    try:
        df = get_exportacao(year, option)
        if country:
            df = df[df["Country"].str.contains(country, case=False, na=False)]
        if product:
            df = df[df["Product"].str.contains(product, case=False, na=False)]
        data = df.to_dict(orient="records")
        logging.info("Dados do site coletados com sucesso")
        return JSONResponse(status_code=200, content={"success": True, "total": len(data), "data": data})
    except Exception as e:
        logging.error(f"Erro ao capturar dados do banco: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    except:
        logging.error("Erro ao capturar dados do site, tentando coletar do banco")

        conn = sqlite3.connect("vitibrasil.db")
        cursor = conn.cursor()

        query = "SELECT Year, Country, Quantity_Kg, Value_USD FROM exportacoes WHERE 1=1" 
        params = [] 

        if year is not None:
            query += " AND Year = ?"
            params.append(year)
        
        if country:
            query += " AND Country LIKE ?"
            params.append(country)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        data = [{"Year": row[0], "Country": row[1], "Quantity_Kg": row[2], "Value_USD": row[3]} for row in rows]
        conn.close()

        return JSONResponse(status_code=200, content={"success": True, "total": len(data), "data": data})

