from rest_framework import serializers


class SubmitTestSerializer(serializers.Serializer):
    gender = serializers.ChoiceField(choices=["M", "F"])
    answers = serializers.DictField(
        child=serializers.ChoiceField(choices=["1", "0", ""])
    )
