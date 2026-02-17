# students/utils.py

def sort_students_by_name(students):
    """
    Sorts a list of student objects by first_name (A-Z).
    """
    return sorted(students, key=lambda s: s.first_name.lower())

def sort_students_by_roll(students):
    """
    Sorts a list of student objects by roll_number (as integer, if possible).
    """
    def roll_sort_key(s):
        roll = s.roll_number
        if not roll:
            return (1, '', 0)  # Put students without roll_number at the end
        if roll.isdigit():
            return (0, '', int(roll))
        return (0, roll, 0)
    return sorted(students, key=roll_sort_key)
