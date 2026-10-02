from app.db.repo import save

def handle(order: str) -> str:
    save(order)
    return order
