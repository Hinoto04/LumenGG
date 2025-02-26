from django.core.exceptions import PermissionDenied

def decorator_with_arguments(decorator):
    """인자가 포함된 함수의 데코레이터 정의용"""
    return lambda *args, **kwargs: lambda func: decorator(func, *args, **kwargs)

@decorator_with_arguments
def permission_required(function, perm):
    """
    권한 확인용 함수
    view에 붙여 사용하여 해당 view에 접근 시, 
    해당 권한이 없으면 PermissionDenied 오류를 발생시킨다.
    """
    def _function(req, *args, **kwargs):
        if req.user.has_perm(perm):
            return function(req, *args, **kwargs)
        else:
            raise PermissionDenied()
    return _function