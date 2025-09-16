import os
import requests
import base64
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import threading

logger = logging.getLogger(__name__)

class MediusPagAPI:
    """
    API wrapper for MEDIUS PAG payment integration
    """
    API_URL = "https://api.mediuspag.com/functions/v1"
    
    def __init__(self, secret_key: str, company_id: str = "30427d55-e437-4384-88de-6ba84fc74833"):
        self.secret_key = secret_key
        self.company_id = company_id
    
    def _get_headers(self) -> Dict[str, str]:
        """Create authentication headers for MEDIUS PAG API"""
        # Create basic auth header as per documentation
        auth_string = f"{self.secret_key}:x"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        return {
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        timestamp = int(datetime.now().timestamp())
        unique_id = str(uuid.uuid4()).replace('-', '')[:8]
        return f"MP{timestamp}{unique_id}"
    
        # Executar em thread separada para não bloquear
        thread = threading.Thread(target=send_webhook)
        thread.daemon = True
        thread.start()
    
    def create_pix_transaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PIX transaction using MEDIUS PAG API"""
        try:
            logger.info("Iniciando criação de transação PIX via MEDIUS PAG...")
            
            # Validar dados obrigatórios
            required_fields = ['amount', 'customer_name', 'customer_cpf']
            missing_fields = []
            for field in required_fields:
                if field not in data or not data[field]:
                    missing_fields.append(field)
            
            if missing_fields:
                raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
            
            # Preparar dados da transação
            transaction_id = self._generate_transaction_id()
            
            # Dados padrão fornecidos pelo usuário
            default_email = "gerarpagamento@gmail.com"
            default_phone = "(11) 98768-9080"
            
            # Testando diferentes estruturas de payload para MEDIUS PAG
            amount_in_cents = int(data['amount'] * 100)  # Converter para centavos
            
            # MEDIUS PAG payload corrigido com campos obrigatórios
            amount_cents = int(data['amount'] * 100)
            
            # Payload completo baseado no padrão MEDIUS PAG/owempay.com.br
            payload = {
                "amount": amount_cents,
                "description": "Nome do Produto",
                "paymentMethod": "PIX",
                "customer": {
                    "name": data.get('customer_name', 'Cliente'),
                    "email": data.get('customer_email', default_email),
                    "phone": data.get('customer_phone', default_phone),
                    "cpf": data.get('customer_cpf', '').replace('.', '').replace('-', '') if data.get('customer_cpf') else None
                },
                "companyId": "30427d55-e437-4384-88de-6ba84fc74833",
                "externalId": transaction_id,
                "postbackUrl": "",  # URL para receber postbacks
                "products": [
                    {
                        "name": "Nome do Produto",
                        "quantity": "Quantidade do Produto (usar apenas numeros}",
                        "price": amount_cents
                    }
                ]
            }
            
            # Remover campos None para evitar erros
            if payload["customer"]["cpf"] is None:
                del payload["customer"]["cpf"]
            
            logger.info(f"Enviando transação PIX: {transaction_id}")
            logger.info(f"Valor: R$ {data['amount']:.2f}")
            logger.info(f"PostbackUrl configurado: {payload['postbackUrl']}")
            logger.info(f"Payload completo: {payload}")
            
            # Fazer requisição para API
            headers = self._get_headers()
            response = requests.post(
                f"{self.API_URL}/transactions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            logger.info(f"Status da resposta MEDIUS PAG: {response.status_code}")
            logger.info(f"Resposta completa MEDIUS PAG: {response.text}")
            
            if response.status_code in [200, 201]:
                try:
                    result = response.json()
                    logger.info(f"Resposta MEDIUS PAG: {json.dumps(result, indent=2)}")
                    
                    # Extrair dados importantes da resposta MEDIUS PAG
                    pix_data = {
                        'success': True,
                        'transaction_id': result.get('id', transaction_id),
                        'order_id': result.get('id', transaction_id),
                        'amount': data['amount'],
                        'status': result.get('status', 'pending'),
                        'created_at': result.get('createdAt', datetime.now().isoformat())
                    }
                    
                    # Buscar PIX code na estrutura de resposta da MEDIUS PAG
                    pix_code_found = False
                    qr_code_found = False
                    
                    # Buscar PIX code na estrutura aninhada da MEDIUS PAG
                    # Baseado nos logs: result["pix"]["qrcode"] é o campo correto
                    if 'pix' in result and isinstance(result['pix'], dict):
                        pix_info = result['pix']
                        
                        # Campo correto da MEDIUS PAG é "qrcode"
                        if 'qrcode' in pix_info and pix_info['qrcode']:
                            pix_data['pix_code'] = pix_info['qrcode']
                            pix_code_found = True
                            logger.info(f"✅ PIX code real MEDIUS PAG encontrado: {pix_info['qrcode'][:50]}...")
                        
                        # Também verificar outros campos possíveis
                        if not pix_code_found and 'pixCopyPaste' in pix_info and pix_info['pixCopyPaste']:
                            pix_data['pix_code'] = pix_info['pixCopyPaste']
                            pix_code_found = True
                            logger.info(f"✅ PIX code real MEDIUS PAG encontrado em pixCopyPaste: {pix_info['pixCopyPaste'][:50]}...")
                        
                        if 'pixQrCode' in pix_info and pix_info['pixQrCode']:
                            pix_data['qr_code_image'] = pix_info['pixQrCode']
                            qr_code_found = True
                            logger.info(f"✅ QR code real MEDIUS PAG encontrado")
                    
                    # Verificar na estrutura principal como fallback
                    if not pix_code_found and 'pixCopyPaste' in result and result['pixCopyPaste']:
                        pix_data['pix_code'] = result['pixCopyPaste']
                        pix_code_found = True
                        logger.info(f"✅ PIX code real MEDIUS PAG encontrado na raiz: {result['pixCopyPaste'][:50]}...")
                    
                    if not qr_code_found and 'pixQrCode' in result and result['pixQrCode']:
                        pix_data['qr_code_image'] = result['pixQrCode']
                        qr_code_found = True
                        logger.info(f"✅ QR code real MEDIUS PAG encontrado na raiz")
                    
                    # Se não encontrou, verificar estruturas alternativas
                    if not pix_code_found:
                        # Outros campos possíveis
                        for field in ['qrCodePix', 'pix_copy_paste', 'copyPaste', 'code']:
                            if field in result and result[field]:
                                pix_data['pix_code'] = result[field]
                                pix_code_found = True
                                logger.info(f"✅ PIX code encontrado em {field}")
                                break
                    
                    if not qr_code_found:
                        # Outros campos possíveis para QR code
                        for field in ['qrCode', 'qr_code_image', 'base64Image']:
                            if field in result and result[field]:
                                pix_data['qr_code_image'] = result[field]
                                qr_code_found = True
                                logger.info(f"✅ QR code encontrado em {field}")
                                break
                    
                    # Log final do que foi encontrado
                    if not pix_code_found and not qr_code_found:
                        logger.warning("Resposta MEDIUS PAG não contém dados PIX válidos")
                    else:
                        logger.info(f"✅ MEDIUS PAG - PIX: {pix_code_found}, QR: {qr_code_found}")
                    
                    # Definir valores padrão vazios se não encontrados
                    if not pix_code_found:
                        pix_data['pix_code'] = ''
                    if not qr_code_found:
                        pix_data['qr_code_image'] = ''
                    
                    # Enviar notificação Pushcut quando transação for criada com sucesso
                    pushcut_data = {
                        'transaction_id': pix_data['transaction_id'],
                        'amount': pix_data['amount'],
                        'customer_name': data.get('customer_name', 'Cliente'),
                        'created_at': pix_data['created_at']
                    }
                    self._send_pushcut_notification(pushcut_data)
                    
                    return pix_data
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Erro ao decodificar resposta JSON: {e}")
                    logger.error(f"Resposta bruta: {response.text}")
                    raise Exception(f"Erro ao processar resposta da API: {e}")
            else:
                error_msg = f"Erro na API MEDIUS PAG - Status: {response.status_code}"
                logger.error(error_msg)
                logger.error(f"Resposta: {response.text}")
                
                # Tentar extrair mensagem de erro da resposta
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = f"Erro MEDIUS PAG: {error_data['message']}"
                    elif 'error' in error_data:
                        error_msg = f"Erro MEDIUS PAG: {error_data['error']}"
                except:
                    pass
                
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conectividade com MEDIUS PAG: {e}")
            raise Exception(f"Erro de conectividade: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao criar transação PIX: {e}")
            raise Exception(f"Erro ao processar pagamento: {str(e)}")
    
    def get_transaction_by_id(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction details by ID from MEDIUS PAG"""
        try:
            logger.info(f"Buscando transação MEDIUS PAG: {transaction_id}")
            
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json",
                "authorization": f'Basic {base64.b64encode(f"{self.secret_key}:x".encode()).decode()}'
            }
            
            response = requests.get(
                f"{self.API_URL}/transactions/{transaction_id}",
                headers=headers,
                timeout=15
            )
            
            logger.info(f"Status da busca MEDIUS PAG: {response.status_code}")
            logger.info(f"Resposta completa: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Transação encontrada: {json.dumps(result, indent=2)}")
                
                # Extrair PIX real da transação MEDIUS PAG
                pix_data = {
                    'success': True,
                    'transaction_id': result.get('id', transaction_id),
                    'order_id': result.get('id', transaction_id),
                    'amount': result.get('amount', 0) / 100,  # Converter de centavos
                    'pix_code': result.get('pixCopyPaste', result.get('pix_copy_paste', result.get('qrCodePix', ''))),
                    'qr_code_image': result.get('pixQrCode', result.get('qr_code_image', result.get('qrCode', ''))),
                    'status': result.get('status', 'pending'),
                    'created_at': result.get('createdAt', ''),
                    'description': result.get('description', 'Receita de bolo')
                }
                
                return pix_data
            else:
                logger.error(f"Erro ao buscar transação: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'Transação não encontrada: {transaction_id}'}
                
        except Exception as e:
            logger.error(f"Erro ao buscar transação: {e}")
            return {'success': False, 'error': str(e)}
    
    def check_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Verifica status da transação usando a nova API confiável"""
        logger.info(f"🔍 Verificando status via webhook manager: {transaction_id}")
        
        try:
            # Nova API de status confiável
            status_endpoint = f"https://webhook-manager.replit.app/api/order/{transaction_id}/status"
            logger.info(f"📡 Consultando: {status_endpoint}")
            
            # Headers simples - API externa não precisa de autenticação MEDIUS PAG
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(status_endpoint, headers=headers, timeout=10)
            logger.info(f"📊 Status webhook manager: {response.status_code}")
            logger.info(f"📋 Response: {response.text}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    status = data.get('status', 'pending').lower()
                    
                    logger.info(f"✅ Status obtido: {status}")
                    
                    if status == 'approved':
                        logger.info("🎉 PAGAMENTO APROVADO! Deve redirecionar para /multa")
                        return {
                            'success': True,
                            'status': 'paid',
                            'transaction_id': transaction_id,
                            'amount': 138.45,  # Valor conhecido
                            'paid_at': data.get('paid_at', ''),
                            'data': data,
                            'redirect_to': '/multa'
                        }
                    elif status == 'pending':
                        logger.info("⏳ Pagamento ainda pendente")
                        return {
                            'success': True,
                            'status': 'waiting_payment',
                            'transaction_id': transaction_id,
                            'amount': 138.45,
                            'paid_at': None,
                            'data': data
                        }
                    else:
                        logger.info(f"ℹ️ Status: {status}")
                        return {
                            'success': True,
                            'status': status,
                            'transaction_id': transaction_id,
                            'amount': 138.45,
                            'paid_at': data.get('paid_at'),
                            'data': data
                        }
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Erro JSON: {e}")
                    return {
                        'success': False,
                        'error': f'Invalid JSON response: {response.text[:200]}'
                    }
                    
            elif response.status_code == 404:
                logger.warning(f"⚠️ Transação não encontrada no webhook manager: {transaction_id}")
                return {
                    'success': True,
                    'status': 'waiting_payment',  # Assumir pendente se não encontrado
                    'transaction_id': transaction_id,
                    'amount': 126.62,
                    'paid_at': None,
                    'data': {'note': 'Transaction not found in webhook manager - assuming pending'}
                }
                
            else:
                logger.error(f"❌ Erro webhook manager: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Webhook manager error: {response.status_code} - {response.text}'
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout na consulta ao webhook manager")
            return {
                'success': False,
                'error': 'Timeout - webhook manager não respondeu'
            }
            
        except requests.exceptions.ConnectionError:
            logger.error("❌ Erro de conexão com webhook manager")
            return {
                'success': False,
                'error': 'Connection error - verificar conectividade com webhook manager'
            }
            
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _format_success_response(self, data: dict, transaction_id: str) -> Dict[str, Any]:
        """Formatar resposta de sucesso padronizada"""
        status = data.get('status', 'pending')
        amount = data.get('amount', 0)
        paid_at = data.get('paidAt') or data.get('paid_at')
        
        return {
            'success': True,
            'status': 'paid' if paid_at else status,
            'transaction_id': transaction_id,
            'amount': amount / 100 if amount else None,
            'paid_at': paid_at,
            'data': data
        }
    
    def _detect_payment_status(self, transaction_data: dict) -> bool:
        """Detecta se pagamento foi realizado com base nos dados disponíveis"""
        # Analisar indicadores de pagamento nos dados da transação
        status = transaction_data.get('status', '').lower()
        
        # Status explícitos que indicam pagamento
        if status in ['paid', 'completed', 'approved', 'success']:
            return True
            
        # Verificar se há data de pagamento
        paid_at = transaction_data.get('paid_at') or transaction_data.get('paidAt')
        if paid_at:
            return True
            
        # Verificar campos que podem indicar pagamento processado
        payment_method = transaction_data.get('paymentMethod', '')
        if payment_method and status not in ['pending', 'waiting', 'created']:
            return True
            
        return False

def create_medius_pag_api(secret_key: Optional[str] = None, company_id: Optional[str] = None) -> MediusPagAPI:
    """Factory function to create MediusPagAPI instance"""
    if not secret_key:
        secret_key = os.environ.get('MEDIUS_PAG_SECRET_KEY')
        if not secret_key:
            raise ValueError("MEDIUS_PAG_SECRET_KEY não encontrada nas variáveis de ambiente")
    
    if not company_id:
        company_id = os.environ.get('MEDIUS_PAG_COMPANY_ID', '30427d55-e437-4384-88de-6ba84fc74833')
    
    # Ensure company_id is not None
    final_company_id = company_id or '30427d55-e437-4384-88de-6ba84fc74833'
    
    return MediusPagAPI(secret_key=secret_key, company_id=final_company_id)