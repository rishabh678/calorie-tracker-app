import streamlit as st
import base64
import json
import os
import time
from datetime import datetime, date
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None

# Optional Anthropic SDK:
# pip install anthropic
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


st.set_page_config(
    page_title="AI Calorie Counter",
    page_icon="🔥",
    layout="centered",
)

STORAGE_FILE = "calorie_counter_data.json"


def today_str():
    return date.today().isoformat()


def time_str(ts):
    return datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")


def uid():
    return os.urandom(5).hex()


def load_data():
    if not os.path.exists(STORAGE_FILE):
        return {"log": [], "goal": 2000}

    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "log": data.get("log", []),
            "goal": data.get("goal", 2000),
        }
    except Exception:
        return {"log": [], "goal": 2000}


def save_data():
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "log": st.session_state.log,
                "goal": st.session_state.goal,
            },
            f,
            indent=2,
        )


def resize_image(uploaded_file, max_width=800, quality=70):
    if Image is None:
        return uploaded_file.getvalue()

    image = Image.open(uploaded_file).convert("RGB")
    scale = min(1, max_width / image.width)

    if scale < 1:
        image = image.resize(
            (round(image.width * scale), round(image.height * scale))
        )

    output = BytesIO()
    image.save(output, format="JPEG", quality=quality)
    return output.getvalue()


def analyze_photo(image_bytes):
    """
    Analyze a food image using Anthropic Claude.

    IMPORTANT:
    Set your API key as an environment variable:
        ANTHROPIC_API_KEY=your_key_here

    Do not put the API key directly in this source code.
    """

    if Anthropic is None:
        raise RuntimeError(
            "Anthropic package is not installed. Run: pip install anthropic"
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured."
        )

    client = Anthropic(api_key=api_key)

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Identify each distinct food item visible in this photo.
Estimate a realistic portion size for each and the calories it contributes,
plus a total.

Respond with ONLY raw JSON, no markdown fences and no commentary.

Use exactly this shape:
{
  "items": [
    {
      "name": "string",
      "portion": "string",
      "calories": number
    }
  ],
  "total_calories": number,
  "confidence": "low" | "medium" | "high"
}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    text = next(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    )

    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def initialize():
    if "initialized" not in st.session_state:
        data = load_data()
        st.session_state.log = data["log"]
        st.session_state.goal = data["goal"]
        st.session_state.pending = None
        st.session_state.initialized = True


def add_analysis(analysis, image_bytes):
    st.session_state.log.insert(
        0,
        {
            "id": uid(),
            "ts": time.time(),
            "image": base64.b64encode(image_bytes).decode("utf-8"),
            "items": analysis.get("items", []),
            "total_calories": analysis.get("total_calories", 0),
            "confidence": analysis.get("confidence", "medium"),
        },
    )
    save_data()


initialize()

# ---------- Header ----------

st.title("🔥 AI Calorie Counter")

today_entries = [
    entry
    for entry in st.session_state.log
    if datetime.fromtimestamp(entry["ts"]).date() == date.today()
]

today_total = sum(
    entry.get("total_calories", 0)
    for entry in today_entries
)

goal = st.session_state.goal
remaining = goal - today_total
percentage = min(1, max(0, today_total / goal if goal else 0))

st.progress(percentage)

col1, col2 = st.columns(2)

with col1:
    st.metric("Today's calories", f"{today_total} kcal")

with col2:
    if remaining >= 0:
        st.metric("Remaining", f"{remaining} kcal")
    else:
        st.metric("Over goal", f"{abs(remaining)} kcal")


# ---------- Goal ----------

with st.expander("🎯 Daily calorie goal"):
    new_goal = st.number_input(
        "Calories per day",
        min_value=1,
        value=int(st.session_state.goal),
        step=50,
    )

    if st.button("Save goal"):
        st.session_state.goal = int(new_goal)
        save_data()
        st.rerun()


# ---------- Photo ----------

st.subheader("📷 Photograph food")

uploaded_file = st.file_uploader(
    "Take a food photo or choose an image",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=False,
)

if uploaded_file is not None:

    image_bytes = resize_image(uploaded_file, 800, 70)

    st.image(image_bytes, caption="Selected food", use_container_width=True)

    if st.button("🤖 Analyze food", type="primary"):

        with st.spinner("Analyzing photo..."):
            try:
                analysis = analyze_photo(image_bytes)

                st.session_state.pending = {
                    "image": image_bytes,
                    "analysis": analysis,
                }

            except Exception as error:
                st.error(f"Could not analyze the photo: {error}")


# ---------- Analysis result ----------

pending = st.session_state.get("pending")

if pending:

    analysis = pending["analysis"]

    st.subheader("Nutrition estimate")

    confidence = analysis.get("confidence", "medium")

    st.write(f"**Confidence:** {confidence}")

    for item in analysis.get("items", []):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.write(
                f"**{item.get('name', 'Unknown')}** "
                f"({item.get('portion', 'unknown portion')})"
            )

        with col2:
            st.write(f"**{item.get('calories', 0)} kcal**")

    st.divider()

    total = analysis.get("total_calories", 0)

    st.subheader(f"Total: {total} kcal")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("➕ Add to today's log", type="primary"):
            add_analysis(analysis, pending["image"])
            st.session_state.pending = None
            st.success("Added to today's log.")
            st.rerun()

    with col2:
        if st.button("✕ Cancel"):
            st.session_state.pending = None
            st.rerun()


# ---------- Today's log ----------

st.subheader("TODAY'S LOG")

if not today_entries:
    st.info("Nothing logged yet — take a photo to get started.")

else:
    for entry in today_entries:

        col1, col2, col3 = st.columns([1, 4, 1])

        with col1:
            if entry.get("image"):
                try:
                    st.image(
                        base64.b64decode(entry["image"]),
                        width=55,
                    )
                except Exception:
                    st.write("🔥")
            else:
                st.write("🔥")

        with col2:
            names = ", ".join(
                item.get("name", "Unknown")
                for item in entry.get("items", [])
            )

            st.write(f"**{names}**")
            st.caption(time_str(entry["ts"]))

        with col3:
            st.write(f"**{entry.get('total_calories', 0)}**")

            if st.button("🗑️", key=f"delete_{entry['id']}"):
                st.session_state.log = [
                    x for x in st.session_state.log
                    if x["id"] != entry["id"]
                ]
                save_data()
                st.rerun()


st.caption(
    "AI estimates are approximate. They can be inaccurate for mixed dishes "
    "or hidden ingredients. Use them as a rough guide rather than a precise "
    "measurement."
)
