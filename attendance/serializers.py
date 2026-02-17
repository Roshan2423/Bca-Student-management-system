 
from rest_framework import serializers

class AttendanceSessionSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    course = serializers.CharField()
    date = serializers.DateField()
    title = serializers.CharField(max_length=200)

class AttendanceSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    session = serializers.CharField()
    student = serializers.CharField()
    is_present = serializers.BooleanField()