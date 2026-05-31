# Bruno Markup Language (.bru) Syntax Guide

Bruno uses a simple, highly readable markup language called **Bru** to represent API requests. Every request is stored as a single `.bru` file, making it easy to track, review, and merge via Git.

This guide provides a comprehensive overview of the syntax structures used in `.bru` files.

---

## 1. Core Meta Block
Every `.bru` file starts with a `meta` block to define its identity and order in the folder.

```bru
meta {
  name: Get User Profile
  type: http
  seq: 1
}
```

*   `name`: The visual name shown in the sidebar.
*   `type`: Type of request (`http` or `graphql`).
*   `seq`: Ordering index within the parent folder.

---

## 2. Request Method & URL
Following the meta block is the HTTP method block, containing the request target and basics.

```bru
get {
  url: {{baseUrl}}/api/v1/users/:id
  body: none
  auth: none
}
```

Supported blocks match standard HTTP verbs: `get`, `post`, `put`, `delete`, `patch`, `options`, `head`.
*   `url`: The endpoint target. Can include environment placeholders e.g., `{{baseUrl}}`.
*   `body`: Payload type (e.g., `none`, `json`, `text`, `form-urlencoded`, `multipart-form`).
*   `auth`: Authentication type (`none`, `basic`, `bearer`, `awsv4`, etc.).

---

## 3. Query & Path Parameters
Parameters are mapped to structural blocks using key-value entries.

### Path Parameters (`params:path`)
Used to fill route wildcards like `:id`.

```bru
params:path {
  id: 42
}
```

### Query Parameters (`params:query`)
Appended to the end of URLs as query strings (e.g., `?status=active&limit=10`).

```bru
params:query {
  status: active
  limit: 10
}
```

---

## 4. HTTP Headers (`headers`)
Define request headers line-by-line.

```bru
headers {
  Content-Type: application/json
  Authorization: Bearer {{token}}
  X-Client-Version: 2.1.0
}
```

---

## 5. Payloads & Body formats

### JSON Payload (`body:json`)
Used when `body: json` is declared in the request block.

```bru
body:json {
  {
    "username": "alex_doe",
    "email": "alex@example.com",
    "roles": ["admin"]
  }
}
```

### Multipart / Form Data (`body:form-urlencoded`)
Used for form submissions.

```bru
body:form-urlencoded {
  username: alex_doe
  password: supersecretpassword
}
```

---

## 6. Verification and Assertions (`tests`)
Bruno has a built-in Javascript runtime for assertions and validation. You can write functional test suites inside a `tests` block using standard syntax.

```bru
tests {
  test("Response status is 200 OK", function() {
    expect(res.getStatus()).to.equal(200);
  });
  
  test("Response body returns valid JSON user object", function() {
    const data = res.getBody();
    expect(data.username).to.equal("alex_doe");
    expect(data.email).to.be.a("string");
  });
}
```

---

## 7. Scripting Hooks (`script`)
For dynamic token exchanges, logging, or setting environment variables before/after a request.

### Pre-request Scripting (`script:pre-request`)
Runs before the request is sent.

```bru
script:pre-request {
  // Set timestamp header
  req.setHeader("X-Timestamp", Date.now().toString());
}
```

### Post-response Scripting (`script:post-response`)
Runs upon receiving the response. Useful for chaining authentication sequences.

```bru
script:post-response {
  // Capture authorization token and set to collection variable
  const data = res.getBody();
  if (data.token) {
    bru.setVar("token", data.token);
  }
}
```
