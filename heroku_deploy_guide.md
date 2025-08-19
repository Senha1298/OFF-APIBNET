# Guia de Deploy no Heroku - Receita Federal Payment Portal

## Arquivos Necessários para Deploy

### 1. requirements.txt
Copie o conteúdo de `heroku_requirements.txt` para um arquivo `requirements.txt` na raiz do projeto:

```
Flask==3.0.3
gunicorn==21.2.0
requests==2.31.0
Pillow==10.3.0
qrcode==7.4.2
email-validator==2.1.1
twilio==9.0.4
psycopg2-binary==2.9.9
```

### 2. Procfile
Crie um arquivo `Procfile` (sem extensão) na raiz do projeto:

```
web: gunicorn main:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

### 3. runtime.txt (opcional)
Especifica a versão do Python:

```
python-3.11.9
```

## Variáveis de Ambiente no Heroku

Configure estas variáveis no dashboard do Heroku (Settings > Config Vars):

```
MEDIUS_PAG_SECRET_KEY=sua_secret_key_aqui
MEDIUS_PAG_COMPANY_ID=seu_company_id_aqui
SESSION_SECRET=uma_chave_secreta_aleatoria_para_sessoes
```

## Possíveis Causas do Erro no Heroku

### 1. **Variáveis de Ambiente NÃO CONFIGURADAS** ⚠️ (Mais Comum)
- **Problema**: MEDIUS_PAG_SECRET_KEY ou MEDIUS_PAG_COMPANY_ID não estão definidas no Heroku
- **Como verificar**: 
  ```bash
  heroku config
  # Deve mostrar:
  # MEDIUS_PAG_SECRET_KEY: ***
  # MEDIUS_PAG_COMPANY_ID: ***
  ```
- **Solução**: Configurar as variáveis exatamente como estão no Replit:
  ```bash
  heroku config:set MEDIUS_PAG_SECRET_KEY=sua_secret_key_real
  heroku config:set MEDIUS_PAG_COMPANY_ID=seu_company_id_real
  heroku config:set SESSION_SECRET=uma_chave_aleatoria_qualquer
  ```

### 2. **Company ID Hardcoded** ⚠️ (Problema Conhecido)
- **Problema**: Código pode estar usando Company ID fixo em vez da variável de ambiente
- **Como identificar**: No logs aparece company ID diferente do configurado
- **Solução**: O código foi corrigido para usar apenas variáveis de ambiente

### 3. **Timeout de APIs Externas** ⚠️
- **Problema**: MEDIUS PAG API pode demorar mais que 30s no Heroku
- **Como identificar**: Error "timeout" nos logs
- **Solução**: Código já configurado com timeout de 30s

### 4. **Port Binding**
- **Problema**: Flask não está usando $PORT do Heroku
- **Como identificar**: App não inicia ou fica inacessível
- **Solução**: main.py já corrigido para usar `os.environ.get("PORT", 5000)`

### 5. **SSL/HTTPS Issues**
- **Problema**: Heroku força HTTPS, algumas APIs podem ter problemas
- **Como identificar**: SSL errors nos logs
- **Solução**: Requests já configurado para trabalhar com HTTPS

### 6. **Threading Problems**
- **Problema**: Heroku pode ter restrições de threading
- **Como identificar**: Pushcut notifications falham
- **Solução**: Threading já implementado com daemon=True

## Comandos para Deploy

```bash
# 1. Inicializar git (se não feito)
git init

# 2. Criar app no Heroku
heroku create seu-app-name

# 3. Configurar variáveis de ambiente
heroku config:set MEDIUS_PAG_SECRET_KEY=sua_key
heroku config:set MEDIUS_PAG_COMPANY_ID=seu_id
heroku config:set SESSION_SECRET=sua_session_secret

# 4. Deploy
git add .
git commit -m "Deploy to Heroku"
git push heroku main

# 5. Ver logs
heroku logs --tail
```

## Debug no Heroku

### Passo 1: Verificar se o App Iniciou
```bash
heroku logs --tail
```
**O que procurar:**
- `Listening at: http://0.0.0.0:$PORT` = ✅ App iniciou
- `Error R10 (Boot timeout)` = ❌ App não iniciou (problema no Procfile/main.py)

### Passo 2: Testar Endpoints de Debug
```bash
# Testar se app responde
curl https://seu-app.herokuapp.com/

# Testar credenciais MEDIUS PAG
curl https://seu-app.herokuapp.com/test-credentials

# Debug completo do ambiente Heroku
curl https://seu-app.herokuapp.com/heroku-debug
```

### Passo 3: Verificar Variáveis de Ambiente
```bash
heroku config
```
**Deve aparecer:**
```
MEDIUS_PAG_SECRET_KEY: ***
MEDIUS_PAG_COMPANY_ID: ***
SESSION_SECRET: ***
```

### Passo 4: Testar Geração de PIX
```bash
# Testar criação de PIX diretamente
curl -X POST https://seu-app.herokuapp.com/generate-pix \
  -H "Content-Type: application/json" \
  -d '{"phone":"11987654321"}'
```

### Passo 5: Análise de Logs
Se o PIX não for gerado, procure nos logs:

**✅ Sinais de Sucesso:**
```
✅ PIX code real MEDIUS PAG encontrado
✅ MEDIUS PAG - PIX: True
✅ Transação MEDIUS PAG criada
```

**❌ Sinais de Erro:**
```
❌ Erro ao criar transação MEDIUS PAG
Timeout durante requisição para MEDIUS PAG
401 Unauthorized (credenciais inválidas)
500 Internal Server Error
```

## Correções Específicas para PIX

### Modificação no app.py para Heroku

Se o erro for relacionado ao binding de porta, adicione esta modificação no main.py:

```python
import os
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
```

### Configuração de Produção

Para produção, desabilite o debug mode e configure logs adequados:

```python
import logging
import os

# Configurar logs para produção
if os.environ.get('HEROKU'):
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)
```

## Teste Local que Simula Heroku

Para testar localmente antes do deploy:

```bash
# Instalar gunicorn
pip install gunicorn

# Testar com gunicorn
gunicorn main:app --bind 0.0.0.0:5000 --workers 1 --timeout 120

# Testar endpoints
curl -X GET http://localhost:5000/test-credentials
```

## Próximos Passos

1. Copie `heroku_requirements.txt` para `requirements.txt`
2. Copie `Procfile_heroku` para `Procfile`
3. Configure as variáveis de ambiente no Heroku
4. Faça o deploy
5. Verifique os logs com `heroku logs --tail`
6. Teste o endpoint `/test-credentials` na URL do Heroku

Se ainda houver erro, compartilhe os logs específicos do Heroku para diagnóstico mais preciso.