def linear_search_students(students, query):
   
    result = []
    query = query.lower()
    for student in students:
        if (query in student.first_name.lower() or
            query in student.last_name.lower() or
            query in student.email.lower() or
            query in student.student_id.lower() or
            (student.phone_number and query in student.phone_number.lower())):
            result.append(student)
    return result

def sort_students_by_name(students):
  
    return sorted(students, key=lambda s: s.first_name.lower())

def sort_students_by_roll(students):
    def roll_sort_key(s):
        roll = s.roll_number
        if not roll:
            return (1, '', 0)
        if roll.isdigit():
            return (0, '', int(roll))
        return (0, roll, 0)
    return sorted(students, key=roll_sort_key)