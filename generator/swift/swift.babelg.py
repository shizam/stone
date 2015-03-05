import os
import shutil

from contextlib import contextmanager

from babelapi.data_type import (
    DataType,
    Float32,
    Float64,
    Int32,
    Int64,
    UInt32,
    UInt64,
    is_any_type,
    is_boolean_type,
    is_composite_type,
    is_list_type,
    is_string_type,
    is_struct_type,
    is_symbol_type,
    is_timestamp_type,
    is_union_type,
    is_numeric_type,
)

from babelapi.generator import CodeGeneratorMonolingual
from babelapi.lang.swift import SwiftTargetLanguage

base = """
/* Autogenerated. Do not edit. */
import Foundation
import SwiftyJSON

"""
class SwiftGenerator(CodeGeneratorMonolingual):
    lang = SwiftTargetLanguage()

    def _docf(self, tag, val):
        return '`{}`'.format(val)

    def generate(self, api):
        cur_folder = os.path.dirname(__file__)
        self.logger.info('Copying BabelSerializers.swift to output folder')
        shutil.copy(os.path.join(cur_folder, 'BabelSerializers.swift'),
                    self.target_folder_path)

        self.logger.info('Copying BabelValidators.swift to output folder')
        shutil.copy(os.path.join(cur_folder, 'BabelValidators.swift'),
                    self.target_folder_path)

        self.logger.info('Copying Client.swift to output folder')
        shutil.copy(os.path.join(cur_folder, 'Client.swift'),
                    self.target_folder_path)

        for namespace in api.namespaces.values():
            path = '{}.swift'.format(self.lang.format_class(namespace.name))
            with self.output_to_relative_path(path):
                self._generate_base_namespace_module(namespace)

    def _generate_base_namespace_module(self, namespace):
        self.emit_raw(base)

        with self.block('public class {}'.format(self.lang.format_class(namespace.name))):
            for data_type in namespace.linearize_data_types():
                if is_struct_type(data_type):
                    self._generate_struct_class(namespace, data_type)
                elif is_union_type(data_type):
                    self._generate_union_type(namespace, data_type)
#            else:
#                raise TypeError('Cannot handle type %r' % type(data_type))
        self._generate_routes(namespace)

    # generation helper methods

    @contextmanager
    def function_block(self, func, args, return_type=None):
        signature = '{}({})'.format(func, args)
        if return_type:
            signature += ' -> {}'.format(return_type)
        with self.block(signature):
            yield

    def _func_args(self, args_list, newlines=False, force_first=False):
        out = []
        first = True
        for k, v in args_list:
            if first and force_first:
                k = "#"+k
            if v is not None:
                out.append('{}: {}'.format(k, v))
            first = False
        sep = ', '
        if newlines:
            sep += '\n' + self.make_indent()
        return sep.join(out)

    @contextmanager
    def class_block(self, thing, protocols=None):
        protocols = protocols or []
        extensions = []

        if isinstance(thing, DataType):
            name = self.class_data_type(thing)
            if thing.supertype:
                extensions.append(self.class_data_type(thing.supertype))
        elif isinstance(thing, basestring):
            name = thing
        else:
            raise TypeError("trying to generate class block for unknown type %r" % thing)

        extensions.extend(protocols)

        extend_suffix = ': {}'.format(', '.join(extensions)) if extensions else ''

        with self.block('public class {}{}'.format(name, extend_suffix)):
            yield

    @contextmanager
    def serializer_block(self, data_type):
        with self.class_block(self.class_data_type(data_type)+'Serializer',
                              protocols=['JSONSerializer']):
            self.emit("public init() { }")
            yield

    @contextmanager
    def serializer_func(self, data_type):
        with self.function_block('public func serialize',
                                 args=self._func_args([('value', self.class_data_type(data_type))]),
                                 return_type='String?'):
            yield

    @contextmanager
    def deserializer_func(self, data_type):
        with self.function_block('public func deserialize',
                                 args=self._func_args([('json', 'JSON')]),
                                 return_type=self.class_data_type(data_type)):
            yield

    def class_data_type(self, data_type):
        return self.lang.format_class(data_type.name)

    def _serializer_class(self, data_type, namespace=None):
        if is_list_type(data_type):
            ret = 'ArraySerializer({})'.format(
                self._serializer_class(data_type.data_type, namespace=namespace))
        elif is_string_type(data_type):
            ret = 'Serialization._StringSerializer'
        elif is_timestamp_type(data_type):
            ret = 'NSDateSerializer("{}")'.format(data_type.format)
        elif is_boolean_type(data_type):
            ret = 'Serialization._BoolSerializer'
        elif isinstance(data_type, Int32):
            ret = 'Serialization._Int32Serializer'
        elif isinstance(data_type, Int64):
            ret = 'Serialization._Int64Serializer'
        elif isinstance(data_type, UInt32):
            ret = 'Serialization._UInt32Serializer'
        elif isinstance(data_type, UInt64):
            ret = 'Serialization._UInt64Serializer'
        elif isinstance(data_type, Float32):
            ret = 'Serialization._Float32Serializer'
        elif isinstance(data_type, Float64):
            ret = 'Serialization._Float64Serializer'
        elif is_composite_type(data_type):
            ret = self.lang.format_class(namespace.name) + '.' if namespace else ''
            ret += self.class_data_type(data_type) + 'Serializer()'

        if data_type.nullable:
            ret = 'NullableSerializer({})'.format(ret)

        return ret

    def _swift_type_mapping(self, data_type, namespace=None, serializer=False):
        suffix = 'Serializer' if serializer else ''
        if is_list_type(data_type):
            ret = 'Array{}<{}>'.format(suffix,
                                       self._swift_type_mapping(data_type.data_type,
                                                                namespace,
                                                                serializer))
        elif is_string_type(data_type):
            ret = 'String' + suffix
        elif is_timestamp_type(data_type):
            ret = 'NSDate' + suffix
        elif is_boolean_type(data_type):
            ret = 'Bool' + suffix
        elif isinstance(data_type, Int32):
            ret = 'Int32' + suffix
        elif isinstance(data_type, Int64):
            ret = 'Int64' + suffix
        elif isinstance(data_type, UInt32):
            ret = 'UInt32' + suffix
        elif isinstance(data_type, UInt64):
            ret = 'UInt64' + suffix
        elif isinstance(data_type, Float32):
            ret = 'Float' + suffix
        elif isinstance(data_type, Float64):
            ret = 'Double' + suffix
        elif is_composite_type(data_type):
            ret = self.lang.format_class(namespace.name) + "." if namespace else ""
            ret += self.class_data_type(data_type) + suffix

        if data_type.nullable:
            if serializer:
                ret = 'NullableSerializer<{}>'.format(ret)
            else:
                ret += '?'
        return ret

    def _determine_validator_type(self, data_type):
        if is_list_type(data_type):
            item_validator = self._determine_validator_type(data_type.data_type)
            if item_validator:
                v = "ArrayValidator({})".format(
                    self._func_args([
                        ("itemValidator", item_validator),
                        ("minItems", data_type.min_items),
                        ("maxItems", data_type.max_items),
                    ])
                )
            else:
                return None
        elif is_numeric_type(data_type):
            v = "ComparableTypeValidator({})".format(
                self._func_args([
                    ("minValue", data_type.min_value),
                    ("maxValue", data_type.max_value),
                ])
            )
        elif is_string_type(data_type):
            v = "StringValidator({})".format(
                self._func_args([
                    ("minLength", data_type.min_length),
                    ("maxLength", data_type.max_length),
                    ("pattern", repr(data_type.pattern) if data_type.pattern else None),
                ])
            )
        else:
            return None

        if data_type.nullable:
            v = "NullableValidator({})".format(v)
        return v

    def _generate_struct_class(self, namespace, data_type):
        if data_type.doc:
            self.emit_wrapped_text(self.process_doc(data_type.doc, self._docf), prefix='/// ')
        else:
            self.emit('/// The {} struct'.format(self.class_data_type(data_type)))
        self.emit('///')
        for f in data_type.fields:
            self.emit('/// :param: {}'.format(self.lang.format_variable(f.name)))
            if f.doc:
                self.emit_wrapped_text(self.process_doc(f.doc, self._docf), prefix='///        ')

        with self.class_block(data_type):
            for field in data_type.fields:
                self.emit('public let {} : {}'.format(
                    self.lang.format_variable(field.name),
                    self._swift_type_mapping(field.data_type),
                ))
            self._generate_struct_init(namespace, data_type)

        self._generate_struct_class_serializer(data_type)

    def _struct_init_args(self, data_type, namespace=None):
        args = []
        for field in data_type.all_fields:
            name = self.lang.format_variable(field.name)
            value = self._swift_type_mapping(field.data_type, namespace=namespace)
            if field.has_default:
                value += ' = {}'.format(self.lang.format_obj(field.default))
            elif field.data_type.nullable:
                value += ' = nil'
            arg = (name, value)
            args.append(arg)
        return args

    def _generate_struct_init(self, namespace, data_type):
        # init method
        args = self._struct_init_args(data_type)
        with self.function_block('public init', self._func_args(args)):
            for field in data_type.fields:
                v = self.lang.format_variable(field.name)
                validator = self._determine_validator_type(field.data_type)
                if validator:
                    self.emit('{}.validate({})'.format(validator, v))
                self.emit('self.{} = {}'.format(v, v))
            if data_type.supertype:
                func_args = [(self.lang.format_variable(f.name),
                              self.lang.format_variable(f.name))
                             for f in data_type.supertype.fields]
                self.emit('super.init({})'.format(self._func_args(func_args)))

    def _generate_struct_class_serializer(self, data_type):
        with self.serializer_block(data_type):
            with self.serializer_func(data_type):
                self.emit("var output : [String] = []")
                for field in data_type.all_fields:
                    self.emit('Serialization.addOutput({})'.format(self._func_args([
                        ("field", '"'+field.name+'"'),
                        ("value", "value."+self.lang.format_variable(field.name)),
                        ("serializer", self._serializer_class(field.data_type)),
                        ("output", "&output"),
                    ])))
                self.emit('return "{"+", ".join(output)+"}"')
            with self.deserializer_func(data_type):
                args = []
                for field in data_type.all_fields:
                    var = self.lang.format_variable(field.name)
                    self.emit('let {} = {}.deserialize(json["{}"])'.format(
                        var,
                        self._serializer_class(field.data_type),
                        field.name,
                    ))

                    args.append((var, var))
                self.emit('return {}({})'.format(
                    self.class_data_type(data_type),
                    self._func_args(args)
                ))

    def _format_tag_type(self, namespace, data_type):
        if is_symbol_type(data_type) or is_any_type(data_type):
            return ''
        else:
            return '({})'.format(self._swift_type_mapping(data_type, namespace))

    def _generate_union_type(self, namespace, data_type):
        if data_type.doc:
            self.emit_wrapped_text(self.process_doc(data_type.doc, self._docf), prefix='/// ')
        else:
            self.emit('/// The {} union'.format(self.class_data_type(data_type)))
        self.emit('///')
        for f in data_type.fields:
            self.emit('/// - {}{}'.format(self.lang.format_class(f.name), ':' if f.doc else ''))
            if f.doc:
                self.emit_wrapped_text(self.process_doc(f.doc, self._docf), prefix='///   ')
        with self.block('public enum {}'.format(self.class_data_type(data_type))):
            for field in data_type.fields:
                typ = self._format_tag_type(namespace, field.data_type)
                self.emit('case {}{}'.format(self.lang.format_class(field.name),
                                                  typ))

        self._generate_union_serializer(data_type)

    def _generate_union_serializer(self, data_type):
        with self.serializer_block(data_type):
            with self.serializer_func(data_type):
                with self.block('switch value'):
                    for field in data_type.fields:
                        case = '.{}'.format(self.lang.format_class(field.name))
                        if is_symbol_type(field.data_type) or is_any_type(field.data_type):
                            ret = '"\\"{}\\""'.format(field.name)
                        else:
                            case += '(let arg)'
                            ret = "Serialization.output({})".format(self._func_args([
                                ("field", '"{}"'.format(field.name)),
                                ("value", "arg"),
                                ("serializer", self._serializer_class(field.data_type)),
                            ]))
                        self.emit('case {}:'.format(case))
                        with self.indent():
                            self.emit('return {}'.format(ret))
            with self.deserializer_func(data_type):
                composites = []
                symbols = []

                for field in data_type.fields:
                    if is_symbol_type(field.data_type) or is_any_type(field.data_type):
                        ret = "return {}.{}".format(
                            self.class_data_type(data_type),
                            self.lang.format_class(field.name)
                        )
                        symbols.append((field.name, ret))
                    else:
                        serializer = self._serializer_class(field.data_type)
                        composites.append((field.name, serializer))
                if symbols:
                    with self.block('if let str = json.string'):
                        with self.block('switch str'):
                            for case, ret in symbols:
                                self.emit('case "{}":'.format(case))
                                with self.indent():
                                    self.emit(ret)
                            self.emit('default:')
                            with self.indent():
                                self.emit('assert(false, "Invalid tag \\"\\(str)\\"")')
                if composites:
                    prefix = 'else ' if symbols else ''
                    with self.block('{}if let d = json.dictionary'.format(prefix)):
                        self.emit('assert(d.count == 1, "Expected 1 key, got \\(d.count)")')

                        with self.block('for (key, val) in d'), self.block('switch key'):
                            for f, serializer in composites:
                                self.emit('case "{}":'.format(f))
                                with self.indent():
                                    self.emit('let obj = {}.deserialize(val)'.format(serializer))
                                    self.emit('return {}.{}(obj)'.format(
                                        self.class_data_type(data_type),
                                        self.lang.format_class(f),
                                    ))
                            self.emit('default:')
                            with self.indent():
                                self.emit('assert(false, "Invalid tag \\"\\(key)\\"")')
                self.emit('assert(false, "Failed to deserialize")')
    def _generate_routes(self, namespace):
        with self.block('extension DropboxClient'):
            for route in namespace.routes:
                self._generate_route(namespace, route)

    STYLE_MAPPING = {
        None: 'Rpc',
        'upload': 'Upload',
        'download': 'Download',
    }

    def _generate_route(self, namespace, route):
        host_ident = route.attrs.get('host', 'meta')

        request_type = self._swift_type_mapping(route.request_data_type, namespace=namespace)

        route_style = route.attrs.get('style')

        if is_struct_type(route.request_data_type):
            arg_list = self._struct_init_args(route.request_data_type, namespace=namespace)
            doc_list = [(self.lang.format_variable(f.name), self.process_doc(f.doc, self._docf))
                        for f in route.request_data_type.fields if f.doc]
        else:
            arg_list = [('request', request_type)]

        if route_style == 'upload':
            arg_list.append(('body', 'NSData'))
            doc_list.append(('body', 'The binary payload to upload'))

        func_name = self.lang.format_method('{}_{}'.format(namespace.name, route.name))
        if route.doc:
            self.emit_wrapped_text(route.doc, prefix='/// ')
        else:
            self.emit_wrapped_text('The {} route'.format(func_name))
        self.emit('///')
        for name, doc in doc_list:
            self.emit('/// :param: {}'.format(name))
            if doc:
                self.emit_wrapped_text(doc, prefix='///        ')

        route_type = self.STYLE_MAPPING[route.attrs.get('style')]

        rtype = self._swift_type_mapping(route.response_data_type,
                                         namespace=namespace, serializer=True)
        etype = self._swift_type_mapping(route.error_data_type,
                                         namespace=namespace, serializer=True)

        with self.function_block('public func {}'.format(func_name),
                                 args=self._func_args(arg_list, force_first=True),
                                 return_type='Dropbox{}Request<{}, {}>'.format(route_type,
                                                                               rtype,
                                                                               etype)):

            if is_struct_type(route.request_data_type):
                args = [(name, name) for name, _ in self._struct_init_args(route.request_data_type)]
                self.emit('let request = {}({})'.format(request_type, self._func_args(args)))

            func_args = [
                ('client', 'self'),
                ('host', '"'+host_ident+'"'),
                ('route', '"/{}/{}"'.format(namespace.name, route.name)),
                ('params', '{}.serialize(request)'.format(
                    self._serializer_class(route.request_data_type, namespace=namespace))),
            ]
            if route_style == 'upload':
                func_args.append(('body', 'body'))

            func_args.extend([
                ('responseSerializer', self._serializer_class(route.response_data_type,
                                                              namespace=namespace)),
                ('errorSerializer', self._serializer_class(route.error_data_type,
                                                           namespace=namespace)),
            ])

            self.emit('return Dropbox{}Request({})'.format(route_type, self._func_args(func_args)))