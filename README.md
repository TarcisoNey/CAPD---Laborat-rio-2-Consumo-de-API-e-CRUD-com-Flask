# CAPD---Laborat-rio-2-Consumo-de-API-e-CRUD-com-Flask
2 atividade avaliativa da matéria de coleta analise e preparação de dados, sobre consumo de apis.
#### REST Countries

API externa utilizada: [REST Countries v5](https://restcountries.com/docs/countries) (`https://api.restcountries.com/countries/v5`).

## Execução do projeto
### 1. Primeira vez (setup)
```bash
python3 -m venv .venv               
source .venv/bin/activate           
pip install -r requirements.txt     
```

### 2. Rodar a aplicação
```bash
source .venv/bin/activate
export RESTCOUNTRIES_API_KEY="sua_chave_aqui"   
python app.py
```

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/coletas` | Coleta os países da API e salva no banco (ignora os que já existem) |
| GET | `/paises` | Lista todos os países |
| GET | `/paises/<codigo>` | Busca um país pelo código de 3 letras (ex: `BRA`) |
| POST | `/paises` | Cadastra um país |
| PUT | `/paises/<codigo>` | Atualiza um país |
| DELETE | `/paises/<codigo>` | Remove um país |
| GET | `/regioes/<regiao>/paises` | Filtra por região (Africa, Americas, Antarctic, Asia, Europe, Oceania) |
| GET | `/paises/populacao?min=&max=` | Filtra por faixa de população |


### Exemplos
```bash
curl -X POST http://127.0.0.1:5000/coletas
curl http://127.0.0.1:5000/paises/BRA
curl http://127.0.0.1:5000/regioes/europe/paises
curl "http://127.0.0.1:5000/paises/populacao?min=1000000&max=10000000"

curl -X POST http://127.0.0.1:5000/paises -H "Content-Type: application/json" \
  -d '{"codigo":"XYZ","nome":"Teste","regiao":"Asia","populacao":1000}'
curl -X PUT http://127.0.0.1:5000/paises/XYZ -H "Content-Type: application/json" \
  -d '{"nome":"Novo Nome","regiao":"Europe","populacao":2000}'
curl -X DELETE http://127.0.0.1:5000/paises/XYZ
```
