import json
import random
import os

def load_deck():
    path = os.path.join(os.path.dirname(__file__), "deck.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def sortear(qtd=1, chance_invertida=0.25):
    """
    Sorteia 'qtd' cartas do deck.
    Por padrão, há 25% de chance de cada carta sair invertida.
    """
    deck = load_deck()
    sorteadas = random.sample(deck, qtd)
    
    resultado = []
    for carta in sorteadas:
        carta_copy = carta.copy()
        # Define se a carta está invertida ou não
        carta_copy['invertida'] = random.random() < chance_invertida
        resultado.append(carta_copy)
        
    return resultado

if __name__ == "__main__":
    print("Sorteio Carta do Dia:")
    print(sortear(1))
    print("\nSorteio 3 Cartas:")
    for i, c in enumerate(sortear(3)):
        print(f"{i+1}. {c['nome']} {'(Invertida)' if c['invertida'] else '(Normal)'}")
