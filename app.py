import streamlit as st
from PIL import Image
from google import genai
import json

# Initialize Gemini Client (replace with your actual API key)
API_KEY = "YOUR_GEMINI_API_KEY"
client = genai.Client(api_key=API_KEY)

st.title("AI Calorie Counter")
st.write("Snap or upload a meal photo to calculate calories automatically.")

# Image Input: Camera or File Upload
source = st.radio("Choose input source:", ["Camera", "File Upload"])

image_file = None
if source == "Camera":
    image_file = st.camera_input("Take a picture of your food")
else:
    image_file = st.file_uploader("Upload food image", type=["jpg", "jpeg", "png"])

if image_file:
    img = Image.open(image_file)
    st.image(img, caption="Target Meal", use_container_width=True)

    if st.button("Analyze Calories"):
        with st.spinner("AI is inspecting your plate..."):
            prompt = """
            Analyze this food image. Identify all items, estimate portion sizes, total calories, and macronutrients.
            Return ONLY raw JSON in this exact structure without markdown fences:
            {
              "totalCalories": 550,
              "proteinGrams": 30,
              "carbsGrams": 45,
              "fatGrams": 15,
              "items": [{"name": "Item name", "portion": "1 cup", "calories": 200}]
            }
            """

            try:
                # Send image and prompt directly to Gemini 2.0 Flash
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[img, prompt]
                )
                
                # Parse JSON output
                clean_json = response.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)

                # Display Results
                st.success(f"Total Estimated Calories: {data['totalCalories']} kcal")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Protein", f"{data['proteinGrams']}g")
                col2.metric("Carbs", f"{data['carbsGrams']}g")
                col3.metric("Fat", f"{data['fatGrams']}g")

                st.subheader("Food Items Breakdown")
                for item in data["items"]:
                    st.write(f"• **{item['name']}** ({item['portion']}): {item['calories']} kcal")

            except Exception as e:
                st.error(f"Error processing image: {e}")