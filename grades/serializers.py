 
from rest_framework import serializers

class AssessmentSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    title = serializers.CharField(max_length=200)
    course = serializers.CharField()

class GradeSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    assessment = serializers.CharField()
    student = serializers.CharField()
    marks_obtained = serializers.FloatField()