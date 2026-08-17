"""Create/reset the prototype Pickle model artifact."""
import pickle
from model import DEFAULT_MODEL, MODEL_PATH

MODEL_PATH.parent.mkdir(exist_ok=True)
with MODEL_PATH.open("wb") as file:
    pickle.dump(DEFAULT_MODEL, file)
print(f"Saved {MODEL_PATH}")
