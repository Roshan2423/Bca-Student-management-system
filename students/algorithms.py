

def binary_search_students(students, query):
    """
    Binary search algorithm for faster student search
    Uses multiple binary searches on different sorted fields
    """
    query = query.lower()
    result = []
    
    # Helper function for binary search on a specific field
    def binary_search_by_field(sorted_students, field_getter, target):
        left, right = 0, len(sorted_students) - 1
        matches = []
        
        while left <= right:
            mid = (left + right) // 2
            field_value = field_getter(sorted_students[mid]).lower()
            
            # Check if target is a substring of the field value
            if target in field_value:
                matches.append(sorted_students[mid])
                
                # Search left side for more matches
                left_idx = mid - 1
                while left_idx >= 0 and target in field_getter(sorted_students[left_idx]).lower():
                    matches.append(sorted_students[left_idx])
                    left_idx -= 1
                
                # Search right side for more matches
                right_idx = mid + 1
                while right_idx < len(sorted_students) and target in field_getter(sorted_students[right_idx]).lower():
                    matches.append(sorted_students[right_idx])
                    right_idx += 1
                
                return matches
            
            elif field_value < target:
                left = mid + 1
            else:
                right = mid - 1
        
        return matches
    
    # Create sorted copies for different fields
    students_by_name = sorted(students, key=lambda s: s.first_name.lower())
    students_by_lastname = sorted(students, key=lambda s: s.last_name.lower())
    students_by_email = sorted(students, key=lambda s: s.email.lower())
    students_by_id = sorted(students, key=lambda s: s.student_id.lower())
    
    # Search in each field using binary search
    name_matches = binary_search_by_field(students_by_name, lambda s: s.first_name, query)
    lastname_matches = binary_search_by_field(students_by_lastname, lambda s: s.last_name, query)
    email_matches = binary_search_by_field(students_by_email, lambda s: s.email, query)
    id_matches = binary_search_by_field(students_by_id, lambda s: s.student_id, query)
    
    # Phone number search (linear for simplicity as it might be None)
    phone_matches = []
    for student in students:
        if student.phone_number and query in student.phone_number.lower():
            phone_matches.append(student)
    
    # Combine all matches and remove duplicates
    all_matches = name_matches + lastname_matches + email_matches + id_matches + phone_matches
    
    # Remove duplicates while preserving order
    seen = set()
    result = []
    for student in all_matches:
        student_id = student.student_id
        if student_id not in seen:
            seen.add(student_id)
            result.append(student)
    
    return result
