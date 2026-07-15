"""
Sincroniza o modelo comercial de creditos no Supabase.

Modelo atual:
- tiragem de 3 cartas custa 50 creditos;
- leitura avulsa libera 100 creditos;
- mensal libera 1.500 creditos;
- anual libera 18.250 creditos.
"""

from dotenv import load_dotenv

import db_client


PRICING_SETTINGS = {
    "reading_cost_energia_do_dia": 0,
    "reading_cost_simples": 25,
    "reading_cost_geral": 25,
    "reading_cost_conselho_espiritual": 25,
    "reading_cost_sim_nao": 25,
    "reading_cost_amor": 50,
    "reading_cost_dinheiro": 50,
    "reading_cost_carreira": 50,
    "reading_cost_tres_cartas": 50,
    "reading_cost_personalizada": 100,
    "reading_cost_premium": 250,
    "credit_model_avulso_credits": 100,
    "credit_model_mensal_credits": 1500,
    "credit_model_anual_credits": 18250,
    "credit_model_tiragem_3_cartas_cost": 50,
    "credit_model_recarga_100_amount": "19.90",
    "credit_model_recarga_300_amount": "49.90",
    "credit_model_recarga_500_amount": "79.90",
    "credit_model_recarga_1500_amount": "199.90",
}


def main() -> int:
    load_dotenv()
    for key, value in PRICING_SETTINGS.items():
        result = db_client.set_setting(key, value)
        if isinstance(result, dict) and result.get("erro"):
            print(f"FAIL {key}: {result['erro']}")
            return 1
        print(f"OK {key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
