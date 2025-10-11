import json
from pprint import pprint


with open("samples.json", "r") as f:
    json_data = json.load(f)

px = "PROFESSIONAL EXPERIENCE"
ult_dict = {}

for resume in json_data:
    ult_res = {}
    sec_keys = (list(resume.keys()).remove(px) if px in resume.keys() else list(resume.keys()))
    for sec_key in sec_keys:
        ult_res[sec_key] = resume[sec_key]
    
    ult_px = {}
    if px in list(dkpn.keys()):
        for exp in dkpn[px]:
            for exp_key in exp.keys():
                if type(exp[exp_key]) == list:

    ult_res[px] = ult_px


# json_output = json.dumps(ult_dict, indent=4, ensure_ascii=False)

# with open("new_resume_data.json", "w", encoding="utf-8") as f:
#     f.write(json_output)
