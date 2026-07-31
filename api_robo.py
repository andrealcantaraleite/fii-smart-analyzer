from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import os # Biblioteca adicionada para ler portas da nuvem

app = Flask(__name__)
# Libera o acesso para qualquer site (necessário para a Vercel conversar com o Render)
CORS(app) 

@app.route('/api/analyze/<ticker>', methods=['GET'])
def analyze(ticker):
    url = f"https://statusinvest.com.br/fundos-imobiliarios/{ticker.lower()}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": "Fundo não encontrado"}), 404
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Limpador Matemático
        def limpar_numero(texto):
            if not texto: return 0.0
            clean = re.sub(r'[^\d,]', '', texto).replace(',', '.')
            try:
                return float(clean)
            except:
                return 0.0

        # Extrator "Sonar"
        def buscar_dado_sonar(termo):
            elementos = soup.find_all(string=re.compile(termo, re.IGNORECASE))
            for el in elementos:
                pai = el.find_parent('div')
                if pai:
                    valor_tag = pai.find(class_='value')
                    if valor_tag:
                        return limpar_numero(valor_tag.get_text(strip=True))
            return 0.0
            
        def buscar_texto_sonar(termo):
            elementos = soup.find_all(string=re.compile(termo, re.IGNORECASE))
            for el in elementos:
                pai = el.find_parent('div')
                if pai:
                    valor_tag = pai.find(class_='value')
                    if valor_tag:
                        return valor_tag.get_text(strip=True)
            return "Indefinido"

        price = buscar_dado_sonar('Valor atual')
        dy = buscar_dado_sonar('Dividend Yield')
        pvp = buscar_dado_sonar('P/VP')
        liquidez = buscar_dado_sonar('Liquidez')
        
        segmento = buscar_texto_sonar('Segmento')
        palavras_papel = ['recebíveis', 'títulos', 'papel', 'val']
        is_papel = any(p in segmento.lower() for p in palavras_papel)

        # Histórico de Cotação Yahoo Finance (API Direta)
        prices = [price] * 6 
        try:
            url_yf = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker.upper()}.SA?range=6mo&interval=1mo"
            res_yf = requests.get(url_yf, headers=headers, timeout=5)
            if res_yf.status_code == 200:
                data_yf = res_yf.json()
                closes = data_yf['chart']['result'][0]['indicators']['quote'][0]['close']
                closes = [c for c in closes if c is not None]
                if len(closes) > 0:
                    prices = [round(c, 2) for c in closes[-6:]]
                    while len(prices) < 6:
                        prices.insert(0, prices[0])
        except Exception as e:
            print("Aviso Yahoo API:", e)

        # Projeção de Rendimentos
        cotas = 100.0
        div_mensal_percent = (dy / 100) / 12 if dy > 0 else 0.008 
        dividends = []
        
        for _ in range(12):
            renda_gerada = cotas * price * div_mensal_percent
            dividends.append(round(renda_gerada, 2))
            cotas += renda_gerada / price 

        data = {
            "name": "Extraído do StatusInvest",
            "type": "Papel" if is_papel else "Tijolo",
            "sector": segmento,
            "price": price,
            "pvp": pvp,
            "dy": dy,
            "liquidity": liquidez,
            "vacancia": 0,
            "dividends": dividends,
            "prices": prices
        }
        
        return jsonify(data)
        
    except Exception as e:
        print("Erro Fatal:", str(e))
        return jsonify({"error": "Erro interno"}), 500

if __name__ == '__main__':
    # Modificação crucial para a nuvem: pegar a porta cedida pelo Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)