# Heroku Troubleshooting - PIX Payment System

## 🚨 ERRO MAIS COMUM: Variáveis de Ambiente

### Verificação Rápida
```bash
heroku config --app seu-app-name
```

**Se não aparecer as variáveis, configure:**
```bash
heroku config:set MEDIUS_PAG_SECRET_KEY=sua_secret_key_real --app seu-app-name
heroku config:set MEDIUS_PAG_COMPANY_ID=seu_company_id_real --app seu-app-name
heroku config:set SESSION_SECRET=qualquer_string_aleatoria --app seu-app-name
```

## 🔍 Diagnóstico Completo

### 1. Testar Conectividade Básica
```bash
curl https://seu-app.herokuapp.com/heroku-debug
```

**Resposta esperada:**
```json
{
  "success": true,
  "debug_info": {
    "heroku_detected": true,
    "environment_vars": {
      "MEDIUS_PAG_SECRET_KEY": "***configured***",
      "MEDIUS_PAG_COMPANY_ID": "***configured***"
    }
  }
}
```

### 2. Testar Credenciais MEDIUS PAG
```bash
curl https://seu-app.herokuapp.com/test-credentials
```

**Resposta esperada:**
```json
{
  "success": true,
  "environment_ready": true,
  "credentials_status": {
    "secret_key_configured": true,
    "company_id_configured": true,
    "api_initialized": true
  }
}
```

### 3. Testar Geração de PIX Real
```bash
curl -X POST https://seu-app.herokuapp.com/generate-pix \
  -H "Content-Type: application/json" \
  -d '{"phone":"11987654321"}'
```

**Resposta esperada (SUCCESS):**
```json
{
  "success": true,
  "transaction_id": "uuid-aqui",
  "pix_code": "00020101021226840014br.gov.bcb.pix...",
  "amount": 138.45
}
```

## ❌ Diagnóstico de Erros

### Erro: "not_set" nas variáveis
```json
{
  "environment_vars": {
    "MEDIUS_PAG_SECRET_KEY": "not_set"
  }
}
```
**Solução:** Configurar as variáveis no Heroku

### Erro: 401 Unauthorized
```
401 Unauthorized (credenciais inválidas)
```
**Causa:** Secret key incorreta
**Solução:** Verificar se a MEDIUS_PAG_SECRET_KEY está correta

### Erro: Company ID não encontrado
```
Company ID not found ou Invalid company
```
**Causa:** MEDIUS_PAG_COMPANY_ID incorreto
**Solução:** Verificar se o Company ID está correto

### Erro: Timeout
```
Timeout durante requisição para MEDIUS PAG
```
**Causa:** API MEDIUS PAG demorou mais que 30s
**Solução:** Tentar novamente - pode ser temporário

### Erro: R10 Boot Timeout
```
Error R10 (Boot timeout) -> Web process failed to bind to $PORT
```
**Causa:** App não conseguiu iniciar
**Solução:** Verificar se main.py e Procfile estão corretos

## 🛠️ Comandos de Reparo

### Re-deploy Forçado
```bash
git commit --allow-empty -m "Force redeploy"
git push heroku main
```

### Restart da Aplicação
```bash
heroku restart --app seu-app-name
```

### Reset das Variáveis
```bash
heroku config:unset MEDIUS_PAG_SECRET_KEY --app seu-app-name
heroku config:unset MEDIUS_PAG_COMPANY_ID --app seu-app-name
heroku config:set MEDIUS_PAG_SECRET_KEY=nova_key --app seu-app-name
heroku config:set MEDIUS_PAG_COMPANY_ID=novo_id --app seu-app-name
```

## 📊 Status Check Completo

Execute todos os comandos em sequência:

```bash
# 1. Verificar se app existe
heroku apps:info --app seu-app-name

# 2. Verificar variáveis
heroku config --app seu-app-name

# 3. Verificar logs recentes
heroku logs --tail --app seu-app-name

# 4. Testar debug endpoint
curl https://seu-app.herokuapp.com/heroku-debug

# 5. Testar credenciais
curl https://seu-app.herokuapp.com/test-credentials

# 6. Testar PIX generation
curl -X POST https://seu-app.herokuapp.com/generate-pix \
  -H "Content-Type: application/json" \
  -d '{"phone":"11987654321"}'
```

## 🎯 Cenário de Sucesso

Quando tudo estiver funcionando, você verá nos logs:

```
✅ Secret key configurado: ***
✅ PIX code real MEDIUS PAG encontrado
✅ MEDIUS PAG - PIX: True, QR: False
✅ Transação MEDIUS PAG criada: uuid-da-transacao
✅ PIX real da MEDIUS PAG obtido
✅ Pushcut notification enviada
```

E o curl retornará um PIX válido começando com `00020101021226840014br.gov.bcb.pix...`

## ⚡ Fix Rápido

Se nada funcionar, execute:

```bash
# 1. Reconfigurar tudo
heroku config:set MEDIUS_PAG_SECRET_KEY=SUA_KEY_AQUI --app seu-app-name
heroku config:set MEDIUS_PAG_COMPANY_ID=SEU_ID_AQUI --app seu-app-name
heroku config:set SESSION_SECRET=qualquer_string --app seu-app-name

# 2. Forçar redeploy
git commit --allow-empty -m "Fix config"
git push heroku main

# 3. Testar
curl https://seu-app.herokuapp.com/test-credentials
```