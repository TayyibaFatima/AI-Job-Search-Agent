from backend.tools.cv_parser import extract_cv_text


cv_path = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"

text = extract_cv_text(cv_path)

print("\nCV TEXT:\n")
print(text)