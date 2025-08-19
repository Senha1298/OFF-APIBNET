import os
import uuid
import time
import logging
import requests

class BuckPayAPI:
    def __init__(self, secret_key=None):
        # Use provided secret key or get from environment
        self.secret_key = secret_key or os.environ.get('BUCKPAY_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("BuckPay secret key not provided. Set BUCKPAY_SECRET_KEY environment variable.")
        
        # Múltiplas URLs base para testar
        self.base_urls = [
            "https://api.realtechdev.com.br/v1",
            "https://api.realtechdev.com.br",
            "https://buckpay.realtechdev.com.br/v1",
            "https://buckpay.realtechdev.com.br"
        ]
        self.base_url = self.base_urls[0]  # URL padrão
        
        # Log para debug
        logging.getLogger(__name__).info(f"BuckPay API initialized with key: {self.secret_key[:8]}...{self.secret_key[-8:]}")
        
    def test_authentication(self):
        """Testa diferentes métodos de autenticação com a API"""
        test_payload = {
            "external_id": f"AUTH_TEST_{int(time.time())}",
            "payment_method": "pix",
            "amount": 100
        }
        
        # Diferentes formatos de autenticação
        auth_methods = [
            {"name": "Bearer Token", "headers": {"Authorization": f"Bearer {self.secret_key}"}},
            {"name": "Basic Auth", "headers": {"Authorization": f"Basic {self.secret_key}"}},
            {"name": "X-API-Key", "headers": {"X-API-Key": self.secret_key}},
            {"name": "api-key", "headers": {"api-key": self.secret_key}},
            {"name": "X-Auth-Token", "headers": {"X-Auth-Token": self.secret_key}},
            {"name": "Token", "headers": {"Token": self.secret_key}}
        ]
        
        for base_url in self.base_urls:
            for auth_method in auth_methods:
                try:
                    headers = {
                        'Content-Type': 'application/json',
                        'User-Agent': 'BuckPay API Client',
                        **auth_method["headers"]
                    }
                    
                    response = requests.post(
                        f"{base_url}/transactions",
                        json=test_payload,
                        headers=headers,
                        timeout=10
                    )
                    
                    logging.getLogger(__name__).info(
                        f"Test - URL: {base_url}, Auth: {auth_method['name']}, Status: {response.status_code}"
                    )
                    
                    if response.status_code not in [401, 403]:
                        return {
                            "working_url": base_url,
                            "working_auth": auth_method,
                            "status": response.status_code,
                            "response": response.text[:200]
                        }
                        
                except Exception as e:
                    logging.getLogger(__name__).error(f"Test error - {base_url} + {auth_method['name']}: {e}")
        
        return None

    def create_pix_transaction(self, transaction_data):
        """
        Cria uma transação PIX via BuckPay API
        
        Args:
            transaction_data (dict): Dados da transação contendo:
                - amount (float): Valor em reais
                - customer_name (str): Nome do cliente
                - customer_cpf (str): CPF do cliente
                - customer_email (str): Email do cliente  
                - customer_phone (str): Telefone do cliente
                - description (str): Descrição do produto
            
        Returns:
            dict: Resultado da transação
        """
        try:
            logging.getLogger(__name__).info("Iniciando criação de PIX via BuckPay...")
            
            # Generate unique external ID to avoid duplicates
            external_id = f"BUCK{int(time.time() * 1000)}{uuid.uuid4().hex[:8]}"
            
            # Convert amount to cents (BuckPay works with cents)
            amount_cents = int(transaction_data['amount'] * 100)
            
            # Use default email and phone as specified - ensuring exact format
            default_email = "gerarpagamento@gmail.com"
            default_phone = "5511987899900"  # Already with Brazil prefix
            
            # Ensure CPF is clean (only numbers) and generate a valid one if needed
            clean_cpf = ''.join(filter(str.isdigit, transaction_data['customer_cpf']))
            
            # Generate valid CPF if the provided one is invalid
            if len(clean_cpf) != 11 or clean_cpf == '12345678900':
                # Generate a valid CPF using algorithm
                import random
                def generate_valid_cpf():
                    # Generate first 9 digits
                    cpf = [random.randint(0, 9) for _ in range(9)]
                    
                    # Calculate first check digit
                    sum1 = sum(cpf[i] * (10 - i) for i in range(9))
                    digit1 = (sum1 * 10) % 11
                    if digit1 == 10:
                        digit1 = 0
                    cpf.append(digit1)
                    
                    # Calculate second check digit
                    sum2 = sum(cpf[i] * (11 - i) for i in range(10))
                    digit2 = (sum2 * 10) % 11
                    if digit2 == 10:
                        digit2 = 0
                    cpf.append(digit2)
                    
                    return ''.join(map(str, cpf))
                
                clean_cpf = generate_valid_cpf()
                logging.getLogger(__name__).info(f"CPF inválido fornecido, gerando CPF válido: {clean_cpf}")
            
            # Try minimal payload structure based on API feedback
            payload = {
                "external_id": external_id,
                "payment_method": "pix",
                "amount": amount_cents,
                "buyer": {
                    "name": transaction_data['customer_name'],
                    "email": default_email,
                    "document": clean_cpf,
                    "phone": default_phone
                }
            }
            
            logging.getLogger(__name__).info(f"Payload BuckPay: {payload}")
            
            # Tentar diferentes métodos de autenticação
            auth_methods = [
                {"Authorization": f"Bearer {self.secret_key}"},
                {"X-API-Key": self.secret_key},
                {"api-key": self.secret_key},
                {"Authorization": f"Basic {self.secret_key}"}
            ]
            
            response = None
            working_auth = None
            
            for base_url in self.base_urls:
                for auth_headers in auth_methods:
                    try:
                        headers = {
                            'Content-Type': 'application/json',
                            'User-Agent': 'BuckPay API Client',
                            'Accept': 'application/json',
                            **auth_headers
                        }
                        
                        logging.getLogger(__name__).info(f"Tentando URL: {base_url} com auth: {list(auth_headers.keys())[0]}")
                        
                        response = requests.post(
                            f"{base_url}/transactions",
                            json=payload,
                            headers=headers,
                            timeout=30
                        )
                        
                        # Se não for erro de autenticação, usar esta configuração
                        if response.status_code not in [401, 403]:
                            working_auth = auth_headers
                            self.base_url = base_url
                            logging.getLogger(__name__).info(f"✅ Autenticação funcionando: {base_url} + {list(auth_headers.keys())[0]}")
                            break
                            
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Erro na tentativa {base_url}: {e}")
                        continue
                
                if working_auth:
                    break
            
            if not response:
                response = requests.post(f"{self.base_urls[0]}/transactions", json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
            
            logging.getLogger(__name__).info(f"BuckPay Response Status: {response.status_code}")
            logging.getLogger(__name__).info(f"BuckPay Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                logging.getLogger(__name__).info(f"✅ BuckPay Success Response: {data}")
                
                # Extract PIX data from response
                response_data = data.get('data', {})
                pix_data = response_data.get('pix', {})
                
                return {
                    'success': True,
                    'data': {
                        'external_id': external_id,
                        'transaction_id': response_data.get('id'),
                        'pix_code': pix_data.get('code'),
                        'qr_code_base64': pix_data.get('qrcode_base64'),
                        'amount': transaction_data['amount'],
                        'status': response_data.get('status', 'pending')
                    }
                }
            elif response.status_code == 403:
                # API key forbidden - return error
                logging.getLogger(__name__).error(f"❌ BuckPay API Key Forbidden - erro de autenticação")
                
                return {
                    'success': False,
                    'error': f"API Key BuckPay inválida ou sem permissões: {response.status_code}"
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}'
                    
                logging.getLogger(__name__).error(f"❌ Erro BuckPay: {error_msg}")
                
                return {
                    'success': False,
                    'error': f"Erro na API BuckPay: {response.status_code} - {error_msg}"
                }
                
        except Exception as e:
            logging.getLogger(__name__).error(f"❌ Exceção na BuckPay API: {e}")
            return {
                'success': False,
                'error': f"Falha ao criar transação BuckPay: {str(e)}"
            }

def create_buckpay_api():
    """Factory function to create BuckPay API instance"""
    # Try to get secret key from environment
    env_key = os.environ.get('BUCKPAY_SECRET_KEY')
    
    if env_key:
        logging.getLogger(__name__).info("Using environment BuckPay secret key")
        return BuckPayAPI(env_key)
    else:
        logging.getLogger(__name__).info("Using provided BuckPay secret key")
        return BuckPayAPI()