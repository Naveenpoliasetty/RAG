from src.utils.date_parser import calculate_total_experience

test_experiences = [
    {"duration": "Jan 2020 - Dec 2020"}, # 1 year approx
    {"duration": "Jan 2022 - Present"},     # Jan 2022 to Jan 2026 = 4 years
    {"duration": "2018-2019"}               # 1 year approx
]

total = calculate_total_experience(test_experiences)
print(f"Test 1 (Mixed): {total} (Expected: ~6+ years)")

test_experiences_2 = [
    {"duration": "May 2015 to June 2018"}, # ~3 years
    {"duration": "07/2018 - 08/2021"}      # ~3 years
]

total_2 = calculate_total_experience(test_experiences_2)
print(f"Test 2 (Format): {total_2} (Expected: ~6+ years)")

test_short = [
    {"duration": "Jan 2025 - Mar 2025"} # 2 months
]
total_3 = calculate_total_experience(test_short)
print(f"Test 3 (Short): {total_3} (Expected: 2 months)")
