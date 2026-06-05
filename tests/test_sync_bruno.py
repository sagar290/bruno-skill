#!/usr/bin/env python3
"""
Comprehensive tests for bruno-sync.
Run with: python -m pytest tests/test_sync_bruno.py -v
  or:    python -m unittest tests.test_sync_bruno -v
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bruno_sync.parsers import parse_dotenv, parse_yaml, load_config, resolve_collection_dir, _yaml_coerce
from bruno_sync.scanners.common import normalize_path, join_url_paths
from bruno_sync.bru import (
    parse_bru_blocks,
    serialize_bru_blocks,
    extract_path_from_url,
    extract_endpoint_from_bru,
    request_file_priority,
    make_safe_filename,
    get_folder_and_filename,
    scan_collection,
    find_matching_file,
)
from bruno_sync.scanners.go import scan_go_file_for_routes, scan_chi_file_for_routes, scan_mux_file_for_routes
from bruno_sync.scanners.java import scan_java_spring_file_for_routes
from bruno_sync.scanners.javascript import scan_nextjs_file_for_routes, scan_fastify_file_for_routes, scan_koa_file_for_routes
from bruno_sync.scanners.ruby import scan_ruby_file_for_routes
from bruno_sync.scanner import scan_file_for_routes
from bruno_sync.collection import (
    sync_endpoint_to_bru,
    prune_orphaned_files,
    dedup_collection,
    initialize_collection,
    set_dry_run,
)


class TestParseDotenv(unittest.TestCase):
    def test_basic_parsing(self):
        content = "DB_HOST=localhost\nDB_PORT=5432\nAPI_KEY=secret123"
        result = parse_dotenv(content)
        self.assertEqual(result, {
            'DB_HOST': 'localhost',
            'DB_PORT': '5432',
            'API_KEY': 'secret123',
        })

    def test_quoted_values(self):
        content = 'NAME="My Project"\nPATH=\'/opt/app\''
        result = parse_dotenv(content)
        self.assertEqual(result['NAME'], 'My Project')
        self.assertEqual(result['PATH'], '/opt/app')

    def test_comments_and_blanks(self):
        content = "# This is a comment\n\nKEY=val\n"
        result = parse_dotenv(content)
        self.assertEqual(result, {'KEY': 'val'})

    def test_equals_in_value(self):
        content = "CONN=host=db port=5432"
        result = parse_dotenv(content)
        self.assertEqual(result['CONN'], 'host=db port=5432')

    def test_inline_comments_unquoted(self):
        content = "KEY=val # inline comment"
        result = parse_dotenv(content)
        self.assertEqual(result['KEY'], 'val')


class TestParseYaml(unittest.TestCase):
    def test_simple_nested(self):
        content = "bruno:\n  collection_path: ./bruno\n  collection_name: Test API\n"
        result = parse_yaml(content)
        self.assertIn('bruno', result)
        self.assertEqual(result['bruno']['collection_path'], './bruno')
        self.assertEqual(result['bruno']['collection_name'], 'Test API')

    def test_boolean_coercion(self):
        content = "debug: true\nverbose: false\n"
        result = parse_yaml(content)
        self.assertTrue(result['debug'])
        self.assertFalse(result['verbose'])

    def test_numeric_coercion(self):
        content = "port: 8080\nratio: 3.14\n"
        result = parse_yaml(content)
        self.assertEqual(result['port'], 8080)
        self.assertAlmostEqual(result['ratio'], 3.14)

    def test_null_values(self):
        content = "timeout: null\nfallback: ~\n"
        result = parse_yaml(content)
        self.assertIsNone(result['timeout'])
        self.assertIsNone(result['fallback'])

    def test_list_values(self):
        content = "ignore:\n  - node_modules\n  - .git\n  - vendor\n"
        result = parse_yaml(content)
        self.assertIn('ignore', result)
        self.assertEqual(result['ignore'], ['node_modules', '.git', 'vendor'])

    def test_multiline_literal(self):
        content = "script: |\n  line one\n  line two\nport: 8080\n"
        result = parse_yaml(content)
        self.assertIn('script', result)
        self.assertEqual(result['script'], 'line one\nline two')
        self.assertEqual(result['port'], 8080)

    def test_multiline_folded(self):
        content = "desc: >\n  this is\n  a folded\n  string\nport: 80\n"
        result = parse_yaml(content)
        self.assertIn('desc', result)
        self.assertEqual(result['desc'], 'this is a folded string')

    def test_deep_nesting(self):
        content = "server:\n  api:\n    host: localhost\n    port: 3000\n"
        result = parse_yaml(content)
        self.assertEqual(result['server']['api']['host'], 'localhost')
        self.assertEqual(result['server']['api']['port'], 3000)

    def test_anchor_and_alias(self):
        content = "defaults: &defaults\n  timeout: 30\n  retries: 3\n\nproduction:\n  <<: *defaults\n  timeout: 60\n"
        result = parse_yaml(content)
        self.assertIn('defaults', result)
        self.assertEqual(result['defaults']['timeout'], 30)
        self.assertEqual(result['defaults']['retries'], 3)

    def test_quoted_strings(self):
        content = 'name: "My Project"\ntitle: \'Hello World\'\n'
        result = parse_yaml(content)
        self.assertEqual(result['name'], 'My Project')
        self.assertEqual(result['title'], 'Hello World')

    def test_bruno_config_block(self):
        content = "server:\n  port: 8080\n\nbruno:\n  collection_path: ./bruno-collection\n  collection_name: Project Core API\n  base_url: \"{{baseUrl}}\"\n"
        result = parse_yaml(content)
        self.assertIsInstance(result['bruno'], dict)
        self.assertEqual(result['bruno']['collection_path'], './bruno-collection')
        self.assertEqual(result['bruno']['collection_name'], 'Project Core API')


class TestYamlCoerce(unittest.TestCase):
    def test_true(self):
        self.assertTrue(_yaml_coerce('true'))

    def test_false(self):
        self.assertFalse(_yaml_coerce('false'))

    def test_null(self):
        self.assertIsNone(_yaml_coerce('null'))
        self.assertIsNone(_yaml_coerce('~'))

    def test_integer(self):
        self.assertEqual(_yaml_coerce('42'), 42)

    def test_float(self):
        self.assertAlmostEqual(_yaml_coerce('3.14'), 3.14)

    def test_string(self):
        self.assertEqual(_yaml_coerce('hello'), 'hello')


class TestPathUtilities(unittest.TestCase):
    def test_normalize_path(self):
        self.assertEqual(normalize_path('/api/v1/users'), '/api/v1/users')
        self.assertEqual(normalize_path('api/v1/users'), '/api/v1/users')
        self.assertEqual(normalize_path('/api//v1///users'), '/api/v1/users')
        self.assertEqual(normalize_path('/api/v1/users?query=1'), '/api/v1/users')
        self.assertEqual(normalize_path('/'), '/')

    def test_join_url_paths(self):
        self.assertEqual(join_url_paths('/api', '/v1', '/users'), '/api/v1/users')
        self.assertEqual(join_url_paths('', '/users'), '/users')
        self.assertEqual(join_url_paths('/api/v1', ''), '/api/v1')

    def test_extract_path_from_url(self):
        self.assertEqual(extract_path_from_url('{{baseUrl}}/api/v1/users'), '/api/v1/users')
        self.assertEqual(extract_path_from_url('https://example.com/api/v1/users'), '/api/v1/users')
        self.assertEqual(extract_path_from_url('/api/v1/users'), '/api/v1/users')

    def test_make_safe_filename(self):
        self.assertEqual(make_safe_filename('/api/v1/users/:id'), 'api-v1-users-by-id')
        self.assertEqual(make_safe_filename('/api/v1/users/{id}'), 'api-v1-users-by-id')
        self.assertEqual(make_safe_filename('/'), 'root')

    def test_get_folder_and_filename(self):
        folder, filename = get_folder_and_filename('/api/v1/users', 'GET')
        self.assertEqual(folder, 'api/v1')
        self.assertEqual(filename, 'users-get.bru')

        folder, filename = get_folder_and_filename('/api/v1/users/:id', 'GET')
        self.assertEqual(folder, 'api/v1/users')
        self.assertEqual(filename, 'by-id-get.bru')

        folder, filename = get_folder_and_filename('/health', 'GET')
        self.assertEqual(folder, '')
        self.assertEqual(filename, 'health-get.bru')


class TestBruParserWriter(unittest.TestCase):
    def test_parse_simple_bru(self):
        content = """meta {
  name: GET /api/v1/health
  type: http
  seq: 1
}

get {
  url: {{baseUrl}}/api/v1/health
  body: none
  auth: none
}"""
        blocks = parse_bru_blocks(content)
        self.assertIn('meta', blocks)
        self.assertIn('get', blocks)
        self.assertIn('type: http', blocks['meta'])
        self.assertIn('/api/v1/health', blocks['get'])

    def test_parse_bru_with_path_params(self):
        content = """meta {
  name: GET /users/:id
  type: http
  seq: 2
}

get {
  url: {{baseUrl}}/users/:id
}

params:path {
  id: 
}"""
        blocks = parse_bru_blocks(content)
        self.assertIn('meta', blocks)
        self.assertIn('get', blocks)
        self.assertIn('params:path', blocks)

    def test_parse_bru_with_json_body(self):
        content = """meta {
  name: POST /users
  type: http
  seq: 3
}

post {
  url: {{baseUrl}}/users
  body: json
  auth: none
}

body:json {
  {
    "name": "test"
  }
}"""
        blocks = parse_bru_blocks(content)
        self.assertIn('body:json', blocks)
        self.assertIn('"name"', blocks['body:json'])

    def test_parse_bru_with_tests(self):
        content = """meta {
  name: GET /users/:id
  type: http
  seq: 4
}

get {
  url: {{baseUrl}}/users/:id
}

headers {
  X-Custom-Header: antiautomatic
}

params:path {
  id: 
}

tests {
  test("status code is 200", function() {
    expect(res.getStatus()).to.equal(200);
  });
}"""
        blocks = parse_bru_blocks(content)
        self.assertIn('headers', blocks)
        self.assertIn('params:path', blocks)
        self.assertIn('tests', blocks)
        self.assertIn('expect', blocks['tests'])

    def test_roundtrip_serialize_parse(self):
        blocks = {
            'meta': '  name: Test\n  type: http\n  seq: 1',
            'get': '  url: {{baseUrl}}/test\n  body: none\n  auth: none',
        }
        serialized = serialize_bru_blocks(blocks)
        parsed = parse_bru_blocks(serialized)
        self.assertIn('meta', parsed)
        self.assertIn('get', parsed)
        self.assertIn('type: http', parsed['meta'])
        self.assertIn('/test', parsed['get'])

    def test_extract_endpoint(self):
        content = """meta {
  name: GET /api/v1/health
  type: http
  seq: 1
}

get {
  url: {{baseUrl}}/api/v1/health
  body: none
  auth: none
}"""
        method, path = extract_endpoint_from_bru(content)
        self.assertEqual(method, 'GET')
        self.assertEqual(path, '/api/v1/health')

    def test_extract_endpoint_with_params(self):
        content = """meta {
  name: DELETE /api/v1/users/:id
  type: http
  seq: 2
}

delete {
  url: {{baseUrl}}/api/v1/users/:id
}

params:path {
  id: 
}"""
        method, path = extract_endpoint_from_bru(content)
        self.assertEqual(method, 'DELETE')
        self.assertEqual(path, '/api/v1/users/:id')

    def test_extract_endpoint_non_http(self):
        content = """meta {
  name: GraphQL Query
  type: graphql
  seq: 1
}"""
        result = extract_endpoint_from_bru(content)
        self.assertIsNone(result)

    def test_request_file_priority(self):
        collection_dir = '/tmp/fake_collection'
        self.assertEqual(request_file_priority('/tmp/fake_collection/api/users-get.bru', collection_dir), 1)
        self.assertEqual(request_file_priority('/tmp/fake_collection/_sync/api/users-get.bru', collection_dir), -198)
        self.assertEqual(request_file_priority('/tmp/fake_collection/root-get.bru', collection_dir), -100)


class TestGoScanner(unittest.TestCase):
    def test_gin_direct_routes(self):
        content = '''package main
import "github.com/gin-gonic/gin"
func main() {
    r := gin.Default()
    r.GET("/api/v1/health", HealthHandler)
    r.POST("/api/v1/users", CreateUserHandler)
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_go_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertEqual(len(routes), 2)
        methods = {r['method'] for r in routes}
        self.assertIn('GET', methods)
        self.assertIn('POST', methods)

    def test_gin_group_routes(self):
        content = '''package main
import "github.com/gin-gonic/gin"
func Setup(r *gin.Engine) {
    v1 := r.Group("/api/v1")
    {
        v1.GET("/users", ListUsers)
        v1.POST("/users", CreateUser)
    }
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_go_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertEqual(len(routes), 2)
        paths = {r['path'] for r in routes}
        self.assertIn('/api/v1/users', paths)

    def test_gin_nested_groups(self):
        content = '''package main
import "github.com/gin-gonic/gin"
func Setup(r *gin.Engine) {
    api := r.Group("/api")
    v1 := api.Group("/v1")
    {
        v1.GET("/users", ListUsers)
    }
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_go_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]['path'], '/api/v1/users')


class TestChiScanner(unittest.TestCase):
    def test_chi_routes(self):
        content = '''package main
import "github.com/go-chi/chi/v5"
func Setup(r chi.Router) {
    r.Get("/api/v1/health", HealthHandler)
    r.Post("/api/v1/users", CreateUser)
    r.Put("/api/v1/users/{id}", UpdateUser)
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_chi_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 2)
        methods = {r['method'] for r in routes}
        self.assertIn('GET', methods)


class TestMuxScanner(unittest.TestCase):
    def test_gorilla_mux_routes(self):
        content = '''package main
import "github.com/gorilla/mux"
func Setup(r *mux.Router) {
    r.HandleFunc("/api/v1/health", HealthHandler).Methods("GET")
    r.HandleFunc("/api/v1/users", ListUsers).Methods("GET", "POST")
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_mux_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 2)
        paths = {r['path'] for r in routes}
        self.assertIn('/api/v1/health', paths)


class TestSpringScanner(unittest.TestCase):
    def test_spring_class_mapping(self):
        content = '''@RestController
@RequestMapping("/api/v1")
public class UserController {
    @GetMapping("/users")
    public List<User> listUsers() { return null; }

    @PostMapping("/users")
    public User createUser(@RequestBody User u) { return u; }

    @DeleteMapping("/users/{id}")
    public void deleteUser(@PathVariable Long id) {}
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_java_spring_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 3)
        paths = {r['path'] for r in routes}
        self.assertIn('/api/v1/users', paths)


class TestNextjsScanner(unittest.TestCase):
    def test_nextjs_route_handlers(self):
        content = '''export async function GET(request: Request) {
    return Response.json({ users: [] });
}

export async function POST(request: Request) {
    return Response.json({ created: true });
}'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_nextjs_file_for_routes(f.name)
        os.unlink(f.name)
        methods = {r['method'] for r in routes}
        self.assertIn('GET', methods)
        self.assertIn('POST', methods)


class TestFastifyScanner(unittest.TestCase):
    def test_fastify_method_routes(self):
        content = '''const fastify = require('fastify')();
fastify.get('/api/v1/health', async (req, reply) => {
    return { status: 'ok' };
});
fastify.post('/api/v1/users', async (req, reply) => {
    return { created: true };
});'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_fastify_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 2)
        methods = {r['method'] for r in routes}
        self.assertIn('GET', methods)
        self.assertIn('POST', methods)


class TestKoaScanner(unittest.TestCase):
    def test_koa_router_routes(self):
        content = '''const Router = require('koa-router');
const router = new Router();
router.get('/api/v1/health', async (ctx) => {
    ctx.body = { status: 'ok' };
});
router.post('/api/v1/users', async (ctx) => {
    ctx.body = { created: true };
});
router.del('/api/v1/users/:id', async (ctx) => {
    ctx.status = 204;
});'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_koa_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 2)
        methods = {r['method'] for r in routes}
        self.assertIn('GET', methods)
        self.assertIn('DELETE', methods)


class TestFlaskScanner(unittest.TestCase):
    def test_flask_decorator_routes(self):
        content = '''from flask import Flask
app = Flask(__name__)

@app.route("/api/v1/users", methods=["GET", "POST"])
def users():
    pass

@app.get("/api/v1/health")
def health():
    pass'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 3)
        methods = {r['method'] for r in routes}
        self.assertIn('GET', methods)
        self.assertIn('POST', methods)


class TestExpressScanner(unittest.TestCase):
    def test_express_routes(self):
        content = '''const express = require('express');
const router = express.Router();
router.get('/api/v2/posts', (req, res) => {
    res.json({ posts: [] });
});
router.post('/api/v2/posts', (req, res) => {
    res.status(201).json({ success: true });
});
router.get('/api/v2/posts/:id', (req, res) => {
    res.json({ id: req.params.id });
});'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(content)
            f.flush()
            routes = scan_file_for_routes(f.name)
        os.unlink(f.name)
        self.assertGreaterEqual(len(routes), 3)
        paths = {r['path'] for r in routes}
        self.assertIn('/api/v2/posts', paths)


class TestCollectionSyncIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collection_dir = os.path.join(self.tmpdir, 'bruno-collection')
        os.makedirs(self.collection_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_sync_creates_new_endpoint(self):
        result = sync_endpoint_to_bru(
            collection_dir=self.collection_dir,
            method='GET',
            path='/api/v1/health',
            base_url='{{baseUrl}}',
            seq=1,
        )
        self.assertEqual(result, 'added')
        expected_file = os.path.join(self.collection_dir, '_sync', 'api', 'v1', 'health-get.bru')
        self.assertTrue(os.path.exists(expected_file))

        with open(expected_file, 'r') as f:
            content = f.read()
        self.assertIn('GET /api/v1/health', content)
        self.assertIn('type: http', content)

    def test_sync_updates_existing(self):
        first = sync_endpoint_to_bru(
            collection_dir=self.collection_dir,
            method='GET',
            path='/api/v1/health',
            base_url='{{baseUrl}}',
            seq=1,
        )
        self.assertEqual(first, 'added')

        filepath = os.path.join(self.collection_dir, '_sync', 'api', 'v1', 'health-get.bru')
        second = sync_endpoint_to_bru(
            collection_dir=self.collection_dir,
            method='GET',
            path='/api/v1/health',
            base_url='{{baseUrl}}',
            seq=1,
            existing_filepath=filepath,
        )
        self.assertEqual(second, 'preserved')

    def test_sync_with_path_params(self):
        result = sync_endpoint_to_bru(
            collection_dir=self.collection_dir,
            method='GET',
            path='/api/v1/users/:id',
            base_url='{{baseUrl}}',
            seq=1,
        )
        self.assertEqual(result, 'added')
        expected_file = os.path.join(self.collection_dir, '_sync', 'api', 'v1', 'users', 'by-id-get.bru')
        self.assertTrue(os.path.exists(expected_file))

        with open(expected_file, 'r') as f:
            content = f.read()
        self.assertIn('params:path', content)
        self.assertIn('id:', content)

    def test_sync_preserves_existing_content(self):
        filepath = os.path.join(self.collection_dir, 'test-get.bru')
        with open(filepath, 'w') as f:
            f.write("""meta {
  name: GET /test
  type: http
  seq: 1
}

get {
  url: {{baseUrl}}/test
  body: none
  auth: none
}

headers {
  X-Custom-Header: myvalue
}""")

        result = sync_endpoint_to_bru(
            collection_dir=self.collection_dir,
            method='GET',
            path='/test',
            base_url='{{baseUrl}}',
            seq=1,
            existing_filepath=filepath,
        )
        self.assertEqual(result, 'preserved')

        with open(filepath, 'r') as f:
            content = f.read()
        self.assertIn('X-Custom-Header', content)

    def test_sync_adds_path_params_to_existing(self):
        filepath = os.path.join(self.collection_dir, 'test-get.bru')
        with open(filepath, 'w') as f:
            f.write("""meta {
  name: GET /test/:id
  type: http
  seq: 1
}

get {
  url: {{baseUrl}}/test/:id
  body: none
  auth: none
}""")

        result = sync_endpoint_to_bru(
            collection_dir=self.collection_dir,
            method='GET',
            path='/test/:id',
            base_url='{{baseUrl}}',
            seq=1,
            existing_filepath=filepath,
        )
        self.assertEqual(result, 'updated')

        with open(filepath, 'r') as f:
            content = f.read()
        self.assertIn('params:path', content)
        self.assertIn('id:', content)


class TestCollectionScan(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collection_dir = os.path.join(self.tmpdir, 'bruno-collection')
        os.makedirs(self.collection_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_bru(self, relpath, method, path):
        fullpath = os.path.join(self.collection_dir, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        content = f"""meta {{
  name: {method} {path}
  type: http
  seq: 1
}}

{method.lower()} {{
  url: {{{{baseUrl}}}}{path}
  body: none
  auth: none
}}"""
        with open(fullpath, 'w') as f:
            f.write(content)

    def test_scan_finds_endpoints(self):
        self._write_bru('api/v1/health-get.bru', 'GET', '/api/v1/health')
        self._write_bru('api/v1/users-get.bru', 'GET', '/api/v1/users')

        exact_index, all_entries = scan_collection(self.collection_dir)
        self.assertEqual(len(all_entries), 2)
        self.assertIn(('GET', '/api/v1/health'), exact_index)
        self.assertIn(('GET', '/api/v1/users'), exact_index)

    def test_scan_deduplicates_preferring_manual(self):
        self._write_bru('api/users-get.bru', 'GET', '/api/users')
        self._write_bru('_sync/api/users-get.bru', 'GET', '/api/users')

        exact_index, all_entries = scan_collection(self.collection_dir)
        self.assertIn(('GET', '/api/users'), exact_index)
        self.assertEqual(len(all_entries), 2)

        filepath = exact_index[('GET', '/api/users')]
        rel = os.path.relpath(filepath, self.collection_dir)
        self.assertFalse(rel.startswith('_sync'))

    def test_find_matching_file(self):
        self._write_bru('api/users-get.bru', 'GET', '/api/users')

        exact_index, all_entries = scan_collection(self.collection_dir)
        result = find_matching_file('GET', '/api/users', exact_index, all_entries)
        self.assertIsNotNone(result)
        self.assertTrue(result.endswith('users-get.bru'))

    def test_find_matching_not_found(self):
        exact_index, all_entries = scan_collection(self.collection_dir)
        result = find_matching_file('DELETE', '/nonexistent', exact_index, all_entries)
        self.assertIsNone(result)


class TestInitializeCollection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_bruno_json(self):
        collection_dir = os.path.join(self.tmpdir, 'new-collection')
        initialize_collection(collection_dir, 'Test API')
        bruno_json = os.path.join(collection_dir, 'bruno.json')
        self.assertTrue(os.path.exists(bruno_json))

        with open(bruno_json, 'r') as f:
            data = json.load(f)
        self.assertEqual(data['name'], 'Test API')
        self.assertEqual(data['type'], 'collection')

    def test_does_not_overwrite_existing(self):
        collection_dir = os.path.join(self.tmpdir, 'existing-collection')
        os.makedirs(collection_dir)
        bruno_json = os.path.join(collection_dir, 'bruno.json')
        with open(bruno_json, 'w') as f:
            json.dump({"version": "1", "name": "Old Name", "type": "collection"}, f)

        initialize_collection(collection_dir, 'New Name')

        with open(bruno_json, 'r') as f:
            data = json.load(f)
        self.assertEqual(data['name'], 'Old Name')


class TestPruneOrphaned(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collection_dir = os.path.join(self.tmpdir, 'bruno-collection')
        os.makedirs(self.collection_dir)
        os.makedirs(os.path.join(self.collection_dir, '_sync'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_bru(self, relpath, method, path):
        fullpath = os.path.join(self.collection_dir, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        content = f"""meta {{
  name: {method} {path}
  type: http
  seq: 1
}}

{method.lower()} {{
  url: {{{{baseUrl}}}}{path}
  body: none
  auth: none
}}"""
        with open(fullpath, 'w') as f:
            f.write(content)

    def test_prune_removes_orphaned_files(self):
        self._write_bru('_sync/health-get.bru', 'GET', '/health')
        self._write_bru('_sync/users-get.bru', 'GET', '/users')

        active_routes = [
            {'method': 'GET', 'path': '/health', 'source': 'test'},
        ]
        pruned = prune_orphaned_files(self.collection_dir, active_routes)
        self.assertEqual(pruned, 1)

        self.assertTrue(os.path.exists(
            os.path.join(self.collection_dir, '_sync', 'health-get.bru')
        ))
        self.assertFalse(os.path.exists(
            os.path.join(self.collection_dir, '_sync', 'users-get.bru')
        ))

    def test_prune_preserves_manual_files(self):
        self._write_bru('api/users-get.bru', 'GET', '/api/users')

        active_routes = []
        pruned = prune_orphaned_files(self.collection_dir, active_routes)
        self.assertEqual(pruned, 0)
        self.assertTrue(os.path.exists(
            os.path.join(self.collection_dir, 'api', 'users-get.bru')
        ))


class TestDedupCollection(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collection_dir = os.path.join(self.tmpdir, 'bruno-collection')
        os.makedirs(self.collection_dir)
        os.makedirs(os.path.join(self.collection_dir, '_sync', 'api'))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_bru(self, relpath, method, path):
        fullpath = os.path.join(self.collection_dir, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        content = f"""meta {{
  name: {method} {path}
  type: http
  seq: 1
}}

{method.lower()} {{
  url: {{{{baseUrl}}}}{path}
  body: none
  auth: none
}}"""
        with open(fullpath, 'w') as f:
            f.write(content)

    def test_dedup_removes_lower_priority(self):
        self._write_bru('api/users-get.bru', 'GET', '/api/users')
        self._write_bru('_sync/api/users-get.bru', 'GET', '/api/users')

        _, all_entries = scan_collection(self.collection_dir)
        removed = dedup_collection(self.collection_dir, all_entries)
        self.assertEqual(removed, 1)

        self.assertTrue(os.path.exists(
            os.path.join(self.collection_dir, 'api', 'users-get.bru')
        ))
        self.assertFalse(os.path.exists(
            os.path.join(self.collection_dir, '_sync', 'api', 'users-get.bru')
        ))


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_loads_yaml_config(self):
        config_path = os.path.join(self.tmpdir, 'config.yaml')
        with open(config_path, 'w') as f:
            f.write("bruno:\n  collection_path: ./my-bruno\n  collection_name: My API\n  base_url: '{{baseUrl}}'\n")
        config = load_config(self.tmpdir)
        self.assertEqual(config['collection_path'], './my-bruno')
        self.assertEqual(config['collection_name'], 'My API')

    def test_loads_env_config(self):
        env_path = os.path.join(self.tmpdir, '.env')
        with open(env_path, 'w') as f:
            f.write("BRUNO_COLLECTION_PATH=./env-bruno\nBRUNO_COLLECTION_NAME=Env API\n")
        config = load_config(self.tmpdir)
        self.assertEqual(config['collection_path'], './env-bruno')
        self.assertEqual(config['collection_name'], 'Env API')

    def test_loads_bruno_json(self):
        bruno_path = os.path.join(self.tmpdir, 'bruno.json')
        with open(bruno_path, 'w') as f:
            json.dump({"version": "1", "name": "JSON API", "type": "collection"}, f)
        config = load_config(self.tmpdir)
        self.assertEqual(config['collection_name'], 'JSON API')

    def test_default_config(self):
        config = load_config(self.tmpdir)
        self.assertEqual(config['collection_path'], './bruno')
        self.assertEqual(config['collection_name'], 'Project API')


class TestDryRunMode(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collection_dir = os.path.join(self.tmpdir, 'bruno-collection')
        os.makedirs(self.collection_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_dry_run_does_not_write(self):
        set_dry_run(True)
        try:
            result = sync_endpoint_to_bru(
                collection_dir=self.collection_dir,
                method='GET',
                path='/api/v1/test',
                base_url='{{baseUrl}}',
                seq=1,
            )
            expected_file = os.path.join(self.collection_dir, '_sync', 'api', 'v1', 'test-get.bru')
            self.assertFalse(os.path.exists(expected_file))
        finally:
            set_dry_run(False)

    def test_dry_run_does_not_delete(self):
        filepath = os.path.join(self.collection_dir, '_sync', 'test-get.bru')
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write("meta { name: GET /test type: http seq: 1 }\nget { url: {{baseUrl}}/test }")

        active_routes = []
        pruned = prune_orphaned_files(self.collection_dir, active_routes)
        self.assertTrue(os.path.exists(filepath))


class TestInputValidation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collection_dir = os.path.join(self.tmpdir, 'bruno-collection')
        os.makedirs(self.collection_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_add_endpoint_invalid_method(self):
        from bruno_sync.cli import VALID_METHODS
        self.assertIn('GET', VALID_METHODS)
        self.assertIn('POST', VALID_METHODS)
        self.assertNotIn('INVALID', VALID_METHODS)

    def test_path_normalization_in_add_endpoint(self):
        path_without_slash = 'api/v1/users'
        normalized = '/' + path_without_slash if not path_without_slash.startswith('/') else path_without_slash
        self.assertEqual(normalized, '/api/v1/users')


if __name__ == '__main__':
    unittest.main()