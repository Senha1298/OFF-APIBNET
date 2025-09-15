import os
import requests
import logging
from datetime import datetime
import uuid
from flask import current_app


class FourMPagamentosAPI:
    """
    API client for 4mpagamentos PIX transactions
    """
    
    def __init__(self):
        self.base_url = "https://4mpagamentos.replit.app/api/v1"
        self.api_key = os.environ.get('FOURMPAGAMENTOS_API_KEY')
        
        if not self.api_key:
            current_app.logger.error("[4MPAG] Chave de API não encontrada nas variáveis de ambiente")
            raise ValueError("FOURMPAGAMENTOS_API_KEY é obrigatória")
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        current_app.logger.info("[4MPAG] API client inicializada com sucesso")
    
    def create_pix_transaction(self, customer_data, amount, phone=None):
        """
        Create a PIX transaction using 4mpagamentos API
        
        Args:
            customer_data (dict): Customer information with keys: nome, cpf, email, phone
            amount (float): Transaction amount in BRL
            phone (str): Customer phone number
        
        Returns:
            dict: Transaction result with success status and PIX data
        """
        try:
            current_app.logger.info(f"[4MPAG] Iniciando criação de transação PIX - Valor: R$ {amount}")
            
            # Prepare customer data
            customer_name = customer_data.get('nome', 'Cliente')
            customer_cpf = customer_data.get('cpf', '').replace('.', '').replace('-', '').replace(' ', '')
            customer_email = customer_data.get('email', 'cliente@email.com')
            customer_phone = phone or customer_data.get('phone', '11999999999')
            
            # Clean phone number (only digits)
            customer_phone = ''.join(filter(str.isdigit, customer_phone))
            
            current_app.logger.info(f"[4MPAG] Dados da transação: Nome={customer_name}, CPF={customer_cpf}, Valor=R${amount}")
            
            # Prepare the payload according to 4mpagamentos documentation
            payload = {
                "amount": amount,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_cpf": customer_cpf,
                "customer_phone": customer_phone,
                "description": f"Pagamento de R$ {amount:.2f}"
            }
            
            current_app.logger.info(f"[4MPAG] Enviando requisição para: {self.base_url}/payments")
            
            # Make the API request
            response = requests.post(
                f"{self.base_url}/payments",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            current_app.logger.info(f"[4MPAG] Resposta recebida - Status: {response.status_code}")
            
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                
                # Log the complete response to understand the structure
                current_app.logger.info(f"[4MPAG] 📋 Resposta completa da API: {data}")
                
                # NEW API STRUCTURE: data is nested inside 'data' field
                api_data = data.get('data', {}) if data.get('success') else data
                
                # Extract transaction ID from new structure
                transaction_id = api_data.get('transaction_id') or api_data.get('id')
                
                # Extract PIX code from new structure
                pix_code = api_data.get('pix_code')
                
                current_app.logger.info(f"[4MPAG] ✅ Transação criada - ID: {transaction_id}")
                current_app.logger.info(f"[4MPAG] 💳 Código PIX extraído: {pix_code}")
                
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'pixCode': pix_code,
                    'pixQrCode': api_data.get('pix_qr_code') or api_data.get('qr_code'),
                    'qr_code_image': api_data.get('qr_code_image') or api_data.get('qrcode_image'),
                    'gateway_id': transaction_id,
                    'order_id': transaction_id,
                    'amount': amount,
                    'status': api_data.get('status', 'pending'),
                    'expires_at': api_data.get('expires_at'),
                    'raw_response': data
                }
            else:
                error_msg = f"Erro na API - Status: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_msg)
                    current_app.logger.error(f"[4MPAG] ❌ Erro da API: {error_data}")
                except:
                    current_app.logger.error(f"[4MPAG] ❌ Erro da API: {response.text}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except requests.RequestException as e:
            current_app.logger.error(f"[4MPAG] ❌ Erro de requisição: {e}")
            return {
                'success': False,
                'error': f'Erro de conexão com a API: {str(e)}'
            }
        except Exception as e:
            current_app.logger.error(f"[4MPAG] ❌ Erro inesperado: {e}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }
    
    def check_transaction_status(self, transaction_id):
        """
        Check the status of a PIX transaction
        
        Args:
            transaction_id (str): The transaction ID to check
            
        Returns:
            dict: Transaction status information
        """
        try:
            url = f"{self.base_url}/transactions/{transaction_id}"
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'status': data.get('status', 'unknown'),
                    'data': data
                }
            else:
                return {
                    'success': False,
                    'error': f'Status code: {response.status_code}'
                }
                
        except Exception as e:
            current_app.logger.error(f"[4MPAG] Erro ao verificar status: {e}")
            return {
                'success': False,
                'error': str(e)
            }


def create_fourmpagamentos_api():
    """Factory function to create FourMPagamentosAPI instance"""
    return FourMPagamentosAPI()