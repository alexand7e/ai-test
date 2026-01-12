# Script de Carregamento de Documentos CLTEC

Este script processa e carrega os documentos do CLTEC na base de conhecimento RAG.

## Pré-requisitos

1. Instale as dependências necessárias:
```bash
pip install python-docx PyPDF2 pandas openpyxl
```

2. Certifique-se de que o Qdrant está rodando e configurado no `.env` (ex.: `QDRANT_URL=http://localhost:6333`)

3. Certifique-se de que a API OpenAI está configurada no `.env`

## Como usar

Execute o script a partir do diretório raiz do projeto:

```bash
python scripts/load_cltec_documents.py
```

Se você estiver rodando via Docker Compose, ele **não carrega automaticamente** ao criar o container. Rode manualmente:

```bash
docker compose exec api python scripts/load_cltec_documents.py
```

O script irá:
1. Processar todos os arquivos em `data/CLTEC/`
2. Extrair texto de arquivos DOCX, PDF, XLSX, TXT e MD
3. Dividir o texto em chunks para melhor recuperação
4. Carregar os chunks no índice RAG `cltec_docs`

## Arquivos processados

- **DOCX**: Documentos Word (legislações, notas metodológicas, etc.)
- **PDF**: Relatórios e documentos em PDF
- **XLSX**: Planilhas Excel com estatísticas
- **TXT/MD**: Textos e markdown

## Notas

- O script divide documentos grandes em chunks de ~1500 caracteres com overlap de 300 caracteres
- Cada chunk mantém metadados sobre o arquivo de origem
- O script usa IDs determinísticos por arquivo+chunk, então reexecutar é idempotente no Qdrant

## Verificação

Após executar o script, você pode verificar os documentos carregados usando:

```bash
curl http://localhost:8000/rag/cltec_docs/stats
```

Ou através da interface web em `/admin`.

