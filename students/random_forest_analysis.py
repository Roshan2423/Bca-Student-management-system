import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class StudentPerformancePredictor:
    
    def __init__(self):
        self.classification_model = RandomForestClassifier(
            n_estimators=3,
            random_state=42,
            max_depth=3,
            n_jobs=1,
            warm_start=False,
            bootstrap=True,
            min_samples_split=2,
            min_samples_leaf=1
        )
        self.regression_model = RandomForestRegressor(
            n_estimators=3,
            random_state=42,
            max_depth=3,
            n_jobs=1,
            warm_start=False,
            bootstrap=True,
            min_samples_split=2,
            min_samples_leaf=1
        )
        self.is_trained = False
        
    def collect_student_data(self):
        from students.models import Student
        from attendance.models import DailyAttendance
        from grades.models import StudentGrade
        from courses.models import AssignmentSubmission
        # MongoDB imports - no need for Django ORM
        
        students_data = []
        
        try:
            students = list(Student.objects.filter(is_active=True))
            
            for student in students:
                # 1. Calculate real attendance percentage
                total_attendance = DailyAttendance.objects.filter(student=student).count()
                present_days = DailyAttendance.objects.filter(student=student, is_present=True).count()
                
                if total_attendance > 0:
                    attendance_percentage = (present_days / total_attendance) * 100
                else:
                    # No attendance records means student never attended classes
                    attendance_percentage = 0.0
                
                # 2. Calculate real average assignment scores
                try:
                    # Get total assignments available in the system
                    from courses.models import Assignment
                    total_assignments_available = Assignment.objects.count()
                    
                    # Get assignments submitted by this student
                    submitted_assignments = AssignmentSubmission.objects.filter(
                        student=student, 
                        submission_file_path__ne=None
                    ).filter(submission_file_path__ne="").count()
                    
                    if total_assignments_available > 0:
                        avg_assignment_score = (submitted_assignments / total_assignments_available) * 100
                    else:
                        avg_assignment_score = 0.0
                except:
                    avg_assignment_score = 0.0
                
                # 3. Calculate real average grade scores
                grades = list(StudentGrade.objects.filter(student=student))
                if len(grades) > 0:
                    total_marks = sum(float(grade.marks_obtained) for grade in grades)
                    avg_grade_score = total_marks / len(grades)
                else:
                    # No grades means student hasn't been evaluated yet
                    avg_grade_score = 0.0
                
                # 4. Calculate pass rate based on grades
                if len(grades) > 0:
                    passing_grades = len([g for g in grades if float(g.marks_obtained) >= 40])  # Assuming 40+ is pass
                    pass_rate = (passing_grades / len(grades)) * 100
                else:
                    pass_rate = 0.0  # No grades means no pass rate
                
                # 5. Calculate total subjects (real count or estimate)
                unique_subjects = set()
                for grade in grades:
                    if hasattr(grade, 'subject') and grade.subject:
                        unique_subjects.add(str(grade.subject))
                total_subjects = len(unique_subjects) if unique_subjects else 5
                
                overall_performance = avg_grade_score
                performance_label = self._categorize_performance(overall_performance)
                pass_fail_label = 1 if pass_rate >= 60 else 0  # 60% pass rate threshold
                
                student_data = {
                    'student_id': str(student.student_id),
                    'student_name': f"{student.first_name} {student.last_name}",
                    'program': student.program,
                    'semester': student.current_semester,
                    'attendance_percentage': round(attendance_percentage, 1),
                    'avg_assignment_score': round(avg_assignment_score, 1),
                    'avg_grade_score': round(avg_grade_score, 1),
                    'pass_rate': round(pass_rate, 1),
                    'total_subjects': total_subjects,
                    'performance_label': performance_label,
                    'pass_fail_label': pass_fail_label,
                    'risk_level': self._calculate_risk_level(attendance_percentage, avg_grade_score)
                }
                
                students_data.append(student_data)
                
        except Exception as e:
            print(f"Error collecting student data: {e}")
            # Fallback to mock data if real data fails
            return self.collect_mock_data()
            
        return students_data
    
    def collect_mock_data(self):
        """Fallback method if real data collection fails"""
        from students.models import Student
        
        students_data = []
        try:
            students = list(Student.objects.filter(is_active=True))
            
            for student in students:
                student_data = {
                    'student_id': str(student.student_id),
                    'student_name': f"{student.first_name} {student.last_name}",
                    'program': student.program,
                    'semester': student.current_semester,
                    'attendance_percentage': 0.0,  # Default for no data
                    'avg_assignment_score': 0.0,  # Default for no data
                    'avg_grade_score': 0.0,  # Default for no data
                    'pass_rate': 0.0,  # Default for no data
                    'total_subjects': 0,  # Default subject count
                    'performance_label': self._categorize_performance(0.0),
                    'pass_fail_label': 0,  # Fail by default with no data
                    'risk_level': self._calculate_risk_level(0.0, 0.0)
                }
                students_data.append(student_data)
        except Exception as e:
            print(f"Error in fallback data collection: {e}")
            
        return students_data
    
    def _categorize_performance(self, score):
        if score >= 75:
            return "High"
        elif score >= 60:
            return "Medium"
        else:
            return "Low"
    
    def _calculate_risk_level(self, attendance, grade_score):
        if attendance < 60 or grade_score < 40:
            return "High Risk"
        elif attendance < 75 or grade_score < 60:
            return "Medium Risk"
        else:
            return "Low Risk"
    
    def train_model(self, data):
        if len(data) < 5:
            return False, "Insufficient data for training (minimum 5 students required)"
        
        try:
            df = pd.DataFrame(data)
            
            features = ['attendance_percentage', 'avg_assignment_score', 'avg_grade_score', 
                       'semester', 'total_subjects', 'pass_rate']
            
            X = df[features].fillna(0)
            
            y_classification = df['pass_fail_label']
            y_regression = df['avg_grade_score']
            
            if len(X) >= 8:
                X_train, X_test, y_train_class, y_test_class = train_test_split(
                    X, y_classification, test_size=0.2, random_state=42
                )
                _, _, y_train_reg, y_test_reg = train_test_split(
                    X, y_regression, test_size=0.2, random_state=42
                )
            else:
                X_train, X_test = X, X
                y_train_class, y_test_class = y_classification, y_classification
                y_train_reg, y_test_reg = y_regression, y_regression
            
            self.classification_model.fit(X_train, y_train_class)
            self.regression_model.fit(X_train, y_train_reg)
            
            class_predictions = self.classification_model.predict(X_test)
            accuracy = accuracy_score(y_test_class, class_predictions)
            
            self.is_trained = True
            self.feature_names = features
            
            return True, f"Model trained successfully! Accuracy: {accuracy:.2%}"
            
        except Exception as e:
            return False, f"Error training model: {str(e)}"
    
    def predict_student_performance(self, student_features):
        if not self.is_trained:
            return None, "Model not trained yet"
        
        try:
            features_array = np.array([[
                student_features['attendance_percentage'],
                student_features['avg_assignment_score'], 
                student_features['avg_grade_score'],
                student_features['semester'],
                student_features['total_subjects'],
                student_features['pass_rate']
            ]])
            
            pass_fail_prob = self.classification_model.predict_proba(features_array)[0]
            predicted_grade = self.regression_model.predict(features_array)[0]
            
            feature_importance = dict(zip(
                self.feature_names, 
                self.classification_model.feature_importances_
            ))
            
            # Handle single class prediction scenario
            if len(pass_fail_prob) == 1:
                # If only one class exists, assume it's the pass class
                pass_probability = 100.0
                fail_probability = 0.0
            else:
                pass_probability = round(pass_fail_prob[1] * 100, 2)
                fail_probability = round(pass_fail_prob[0] * 100, 2)
            
            prediction_result = {
                'pass_probability': pass_probability,
                'fail_probability': fail_probability,
                'predicted_grade_score': round(predicted_grade, 2),
                'predicted_performance': self._categorize_performance(predicted_grade),
                'feature_importance': feature_importance
            }
            
            return prediction_result, "Prediction successful"
            
        except Exception as e:
            return None, f"Prediction error: {str(e)}"
    
    def analyze_all_students(self):
        start_time = datetime.now()
        
        students_data = self.collect_student_data()
        
        if not students_data:
            return {
                'success': False,
                'message': 'No student data found',
                'data': []
            }
        
        train_success, train_message = self.train_model(students_data)
        
        if not train_success:
            return {
                'success': False,
                'message': train_message,
                'data': students_data
            }
        
        for student in students_data:
            prediction, pred_message = self.predict_student_performance(student)
            if prediction:
                student.update(prediction)
        
        total_students = len(students_data)
        high_risk = len([s for s in students_data if s['risk_level'] == 'High Risk'])
        medium_risk = len([s for s in students_data if s['risk_level'] == 'Medium Risk'])
        low_risk = len([s for s in students_data if s['risk_level'] == 'Low Risk'])
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        summary = {
            'total_students': total_students,
            'high_risk_count': high_risk,
            'medium_risk_count': medium_risk, 
            'low_risk_count': low_risk,
            'model_accuracy': train_message,
            'processing_time': f"{processing_time:.2f} seconds",
            'analysis_date': end_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        print(f"Generating results... Analysis completed in {processing_time:.2f} seconds!")
        
        return {
            'success': True,
            'message': f'Random Forest analysis completed in {processing_time:.2f} seconds!',
            'summary': summary,
            'students_data': students_data
        }


def run_random_forest_analysis():
    predictor = StudentPerformancePredictor()
    return predictor.analyze_all_students()