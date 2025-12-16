import paho.mqtt.client as mqtt
import random

# -------------------
# FUNÇÃO EXTRA (PRINT)
# -------------------

def print_message_info(message):
    print("Message received:", message.payload.decode("utf-8"))
    print("Message topic:", message.topic)
    print("Message qos:", message.qos)
    print("Message retain flag:", message.retain)

# -------------------
# FUNÇÕES DE RESPOSTA
# -------------------

def get_random_joke():
    jokes = [
        "Why do not skeletons fight each other? They do not have the guts.",
        "I tried to catch fog yesterday… Mist!",
        "Why was the math book sad? Because it had too many problems.",
        "Parallel lines have so much in common. It's a shame they'll never meet."
    ]
    return random.choice(jokes)

# -------------------
# CALLBACKS
# -------------------

def on_connect(client, userdata, flags, reason_code, properties):
    print("Connected:", reason_code)
    client.subscribe("george/test/board")

def on_message(client, userdata, message):

    text = message.payload.decode().strip()
    incoming = text.lower()

    print(f"Received: {text}")

    # 1️⃣ Do NOT reply to own messages
    # We tag our own messages with a prefix
    if incoming.startswith("from-subscriber:"):
        return  # ignore own messages

    # 2️⃣ If it's not a known command → do nothing
    if incoming == "ping":
        reply = "pong"

    elif incoming == "tell a joke":
        reply = get_random_joke()

    elif incoming == "bye":
        reply = "Goodbye!"

    else:
        return  # no reply, no loop

    # 3️⃣ Publish reply with a tag so we don't reply to ourselves
    client.publish("george/test/board", "from-subscriber: " + reply)
    print("Replied:", reply)

# -------------------
# MQTT CLIENT
# -------------------

client = mqtt.Client(
    client_id="subscriber-bot",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

client.on_connect = on_connect
client.on_message = on_message

client.connect("yurir.org", 1883, 60)
client.loop_forever()