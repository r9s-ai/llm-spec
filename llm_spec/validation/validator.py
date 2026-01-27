"""响应验证器"""

from typing import Any, Type, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError


class ResponseValidator:
    """响应验证器，使用 Pydantic 进行验证"""

    @staticmethod
    def _extract_all_fields(
        schema_class: Type[BaseModel],
        prefix: str = "",
        visited: set[Type[BaseModel]] | None = None,
    ) -> list[str]:
        """递归提取 Pydantic schema 的所有字段路径

        Args:
            schema_class: Pydantic schema 类
            prefix: 当前字段路径前缀
            visited: 已访问的类型集合（防止循环引用）

        Returns:
            所有字段路径列表
        """
        if visited is None:
            visited = set()

        # 防止循环引用
        if schema_class in visited:
            return []
        visited.add(schema_class)

        fields = []

        for field_name, field_info in schema_class.model_fields.items():
            # 构建当前字段路径
            field_path = f"{prefix}.{field_name}" if prefix else field_name
            fields.append(field_path)

            # 获取字段类型
            field_type = field_info.annotation
            origin = get_origin(field_type)

            # 处理 Optional[T] / T | None -> 提取 T
            # 在 Python 3.10+, T | None 创建 types.UnionType
            # get_origin() 会返回 types.UnionType 或 Union
            if origin is Union or (origin is not None and str(origin) == "<class 'types.UnionType'>"):
                # 过滤掉 NoneType，获取实际类型
                actual_types = [
                    t for t in get_args(field_type) if t is not type(None)
                ]
                if actual_types:
                    field_type = actual_types[0]
                    origin = get_origin(field_type)  # 重新获取 origin

            # 处理 list[T]
            if origin is list:
                inner_type = get_args(field_type)[0]
                if isinstance(inner_type, type) and issubclass(inner_type, BaseModel):
                    # 递归提取 list 元素的字段
                    nested_fields = ResponseValidator._extract_all_fields(
                        inner_type, field_path, visited.copy()
                    )
                    fields.extend(nested_fields)
                continue  # list 的元素已处理，跳过后续的 BaseModel 检查

            # 处理嵌套的 BaseModel
            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                nested_fields = ResponseValidator._extract_all_fields(
                    field_type, field_path, visited.copy()
                )
                fields.extend(nested_fields)

        return fields

    @staticmethod
    def validate(
        data: dict[str, Any], schema_class: Type[BaseModel]
    ) -> tuple[bool, str | None, list[str], list[str]]:
        """验证响应数据

        Args:
            data: 响应数据
            schema_class: Pydantic schema 类

        Returns:
            (is_valid, error_message, missing_fields, expected_fields)
            - is_valid: 是否验证通过
            - error_message: 错误消息（如果有）
            - missing_fields: 缺失的字段列表
            - expected_fields: 期望的字段列表（从 schema 提取）
        """
        # 递归提取所有期望字段（包括嵌套字段）
        expected_fields = ResponseValidator._extract_all_fields(schema_class)

        try:
            schema_class(**data)
            return True, None, [], expected_fields
        except ValidationError as e:
            # 提取缺失字段
            missing_fields = []
            for error in e.errors():
                if error["type"] == "missing":
                    field_path = ".".join(str(loc) for loc in error["loc"])
                    missing_fields.append(field_path)

            error_message = str(e)
            return False, error_message, missing_fields, expected_fields
