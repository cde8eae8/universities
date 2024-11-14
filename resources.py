import json

def store_universities(universities):
    with open('universities.json', 'w') as f:
        return json.dump(universities, f)

def load_universities():
    with open('universities.json', 'r') as f:
        return json.load(f)

def store_rankings(rankings):
    with open('rankings.json', 'w') as f:
        return json.dump(rankings, f)

def load_rankings():
    with open('rankings.json', 'r') as f:
        return json.load(f)