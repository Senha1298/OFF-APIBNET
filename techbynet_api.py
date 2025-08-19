import os
import requests
import json
import uuid
from datetime import datetime
from flask import current_app

class TechByNetAPI:
    def __init__(self, api_key=None):
        self.base_url = "https://api-gateway.techbynet.com"
        self.api_key = api_key or os.environ.get('TECHBYNET_API_KEY')
        self.headers = {
            'x-api-key': self.api_key,
            'User-Agent': 'AtivoB2B/1.0',
            'Content-Type': 'application/json'
        }
        
        if not self.api_key:
            current_app.logger.warning("[TECHBYNET] API Key não encontrada")



    def create_pix_transaction(self, customer_data, amount, phone=None, postback_url=None):
        """
        Cria uma transação PIX usando a API TechByNet com dados padrão
        Primeiro tenta criar o cliente, depois a transação
        
        Args:
            customer_data: Dict com dados do cliente (nome, cpf, email, etc)
            amount: Valor em reais (float)
            phone: Telefone do cliente
            postback_url: URL para webhook de notificações
            
        Returns:
            Dict com resposta da API ou None em caso de erro
        """
        try:
            current_app.logger.info(f"[TECHBYNET] Iniciando criação de transação PIX - Valor: R$ {amount}")
            
            # Converter valor para centavos
            amount_cents = int(float(amount) * 100)
            
            # Usar dados reais do cliente fornecidos
            customer_name = customer_data.get('nome', 'João Silva Santos')
            customer_email = customer_data.get('email', 'joao.silva@email.com')
            customer_cpf = customer_data.get('cpf', '11144477735').replace('.', '').replace('-', '')  # Remover formatação
            
            # Usar telefone fornecido ou fallback
            customer_phone = phone or customer_data.get('phone', '11987654321')
            
            current_app.logger.info(f"[TECHBYNET] Usando dados reais: Nome={customer_name}, CPF={customer_cpf}, Phone={customer_phone}")
            # Limpar telefone (apenas números)
            customer_phone = ''.join(filter(str.isdigit, customer_phone))
            
            # TechByNet não precisa de criação prévia de cliente
            # A API cria automaticamente quando customer.id não é fornecido
            current_app.logger.info("[TECHBYNET] TechByNet criará cliente automaticamente durante transação")
            
            # URL de postback padrão se não fornecida
            if not postback_url:
                postback_url = f"{os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000')}/techbynet-webhook"
            
            # Gerar external_ref único
            external_ref = f"TBN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Payload para criação de transação
            payload = {
                "amount": amount_cents,
                "currency": "BRL",
                "paymentMethod": "PIX",
                "installments": 1,
                "postbackUrl": postback_url,
                "metadata": json.dumps({
                    "source": "receita_federal_portal",
                    "external_ref": external_ref
                }),
                "traceable": True,
                "ip": "192.168.1.1",  # IP padrão para desenvolvimento
                "customer": {
                    "name": customer_name,
                    "email": customer_email,
                    "document": {
                        "number": customer_cpf,
                        "type": "CPF"
                    },
                    "phone": customer_phone,
                    "externalRef": external_ref,
                    "address": {
                        "street": "Rua Principal",
                        "streetNumber": "123",
                        "complement": "",
                        "zipCode": "01000-000",
                        "neighborhood": "Centro",
                        "city": "São Paulo",
                        "state": "SP",
                        "country": "BR"
                    }
                },
                "items": [
                    {
                        "title": "Mindset avançado",
                        "unitPrice": amount_cents,
                        "quantity": 1,
                        "tangible": False,
                        "externalRef": external_ref
                    }
                ],
                "pix": {
                    "expiresInDays": 1  # PIX expira em 1 dia
                }
            }
            
            current_app.logger.info(f"[TECHBYNET] Enviando payload para API: {json.dumps(payload, indent=2)}")
            
            # Fazer requisição para API
            endpoint = f"{self.base_url}/api/user/transactions"
            current_app.logger.info(f"[TECHBYNET] Enviando POST para: {endpoint}")
            
            response = requests.post(
                endpoint,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            current_app.logger.info(f"[TECHBYNET] Status da resposta: {response.status_code}")
            current_app.logger.info(f"[TECHBYNET] Headers da resposta: {dict(response.headers)}")
            
            if response.status_code == 200:
                response_data = response.json()
                current_app.logger.info(f"[TECHBYNET] Resposta da API: {json.dumps(response_data, indent=2)}")
                
                # Extrair dados relevantes da resposta
                transaction_data = response_data.get('data', {})
                
                result = {
                    'success': True,
                    'transaction_id': transaction_data.get('id'),
                    'external_ref': transaction_data.get('externalRef'),
                    'status': transaction_data.get('status'),
                    'amount': amount,
                    'qr_code': transaction_data.get('qrCode'),
                    'pix_code': transaction_data.get('qrCode'),  # Para compatibilidade
                    'payment_url': transaction_data.get('payUrl'),
                    'expires_at': transaction_data.get('pix', {}).get('expirationDate') if transaction_data.get('pix') else None,
                    'provider': 'TechByNet',
                    'raw_response': response_data
                }
                
                current_app.logger.info(f"[TECHBYNET] Transação criada com sucesso - ID: {result['transaction_id']}")
                return result
                
            else:
                error_text = response.text
                current_app.logger.error(f"[TECHBYNET] Erro na API - Status: {response.status_code}, Resposta: {error_text}")
                
                # Se retornar "Cliente não encontrado", usar PIX brasileiro como fallback
                if "Cliente não encontrado" in error_text:
                    current_app.logger.info("[TECHBYNET] Cliente não encontrado, gerando PIX brasileiro como fallback")
                    
                    try:
                        from brazilian_pix import create_brazilian_pix_provider
                        
                        pix_provider = create_brazilian_pix_provider()
                        pix_result = pix_provider.create_pix_payment(
                            amount=amount,
                            customer_name=customer_name,
                            customer_cpf=customer_cpf,
                            customer_email=customer_email
                        )
                        
                        if pix_result.get('success'):
                            current_app.logger.info("[TECHBYNET] PIX brasileiro gerado com sucesso como fallback")
                            
                            # Adaptar resposta para formato TechByNet
                            return {
                                'success': True,
                                'transaction_id': pix_result.get('order_id', pix_result.get('external_id')),
                                'external_ref': external_ref,
                                'status': 'pending',
                                'amount': amount,
                                'qr_code': pix_result.get('pix_code'),
                                'pix_code': pix_result.get('pix_code'),
                                'payment_url': None,
                                'expires_at': None,
                                'provider': 'TechByNet (Brazilian PIX Fallback)',
                                'qr_code_base64': pix_result.get('qr_code_base64'),
                                'raw_response': pix_result
                            }
                        else:
                            current_app.logger.error(f"[TECHBYNET] Fallback PIX brasileiro também falhou: {pix_result}")
                    
                    except Exception as fallback_error:
                        current_app.logger.error(f"[TECHBYNET] Erro no fallback PIX brasileiro: {fallback_error}")
                
                return {
                    'success': False,
                    'error': f"Erro da API TechByNet: {response.status_code}",
                    'details': error_text,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            current_app.logger.error("[TECHBYNET] Timeout na requisição para API")
            return {
                'success': False,
                'error': "Timeout na comunicação com TechByNet",
                'details': "A requisição demorou mais que 30 segundos"
            }
            
        except requests.exceptions.ConnectionError as e:
            current_app.logger.error(f"[TECHBYNET] Erro de conexão: {e}")
            return {
                'success': False,
                'error': "Erro de conexão com TechByNet",
                'details': str(e)
            }
            
        except Exception as e:
            current_app.logger.error(f"[TECHBYNET] Erro inesperado: {e}")
            return {
                'success': False,
                'error': "Erro interno na integração TechByNet",
                'details': str(e)
            }

    def check_transaction_status(self, transaction_id):
        """
        Verifica o status de uma transação
        
        Args:
            transaction_id: ID da transação para verificar
            
        Returns:
            Dict com status da transação ou None em caso de erro
        """
        try:
            endpoint = f"{self.base_url}/api/user/transactions/{transaction_id}"
            current_app.logger.info(f"[TECHBYNET] Verificando status da transação: {transaction_id}")
            
            response = requests.get(
                endpoint,
                headers=self.headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                transaction = data.get('data', {})
                
                return {
                    'success': True,
                    'transaction_id': transaction.get('id'),
                    'status': transaction.get('status'),
                    'paid_at': transaction.get('paidAt'),
                    'amount': transaction.get('amount', 0) / 100,  # Converter de centavos
                    'provider': 'TechByNet'
                }
            else:
                current_app.logger.error(f"[TECHBYNET] Erro ao verificar status - Status: {response.status_code}")
                return {
                    'success': False,
                    'error': f"Erro ao verificar status: {response.status_code}"
                }
                
        except Exception as e:
            current_app.logger.error(f"[TECHBYNET] Erro ao verificar status: {e}")
            return {
                'success': False,
                'error': str(e)
            }

def create_techbynet_api(api_key=None):
    """
    Factory function para criar instância da API TechByNet
    
    Args:
        api_key: Chave da API (opcional, usa variável de ambiente se não fornecida)
        
    Returns:
        Instância da classe TechByNetAPI
    """
    return TechByNetAPI(api_key)