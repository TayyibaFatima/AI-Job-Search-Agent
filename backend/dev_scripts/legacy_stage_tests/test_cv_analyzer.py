from backend.tools.cv_parser import extract_cv_text
from backend.tools.cv_analyzer import analyze_cv


cv_path = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"


cv_text = extract_cv_text(cv_path)

profile = analyze_cv(cv_text)


print("\nCANDIDATE PROFILE\n")
print(profile.model_dump_json(indent=2))