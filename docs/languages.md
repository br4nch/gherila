# HTTP clients in other languages

Start `gherila-api` first. These examples use its loopback address and public
GitHub adapter. When `GHERILA_API_KEY` is set, add the `X-API-Key` header.
For remote deployments use an HTTPS URL. All examples consume the same JSON API;
no language-specific rewrite of the scrapers is required.

## Go

```go
package main

import (
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

func main() {
    client := &http.Client{Timeout: 65 * time.Second}
    response, err := client.Get("http://127.0.0.1:8000/v1/github/get_user?username=br4nch")
    if err != nil { panic(err) }
    defer response.Body.Close()
    if response.StatusCode != http.StatusOK { panic(response.Status) }
    var user struct { ID string `json:"id"`; Login string `json:"login"` }
    if err := json.NewDecoder(response.Body).Decode(&user); err != nil { panic(err) }
    fmt.Println(user.Login, user.ID)
}
```

## Java 11+

```java
import java.net.URI;
import java.net.http.*;
import java.time.Duration;

class Example {
    public static void main(String[] args) throws Exception {
        var client = HttpClient.newHttpClient();
        var request = HttpRequest.newBuilder()
            .uri(URI.create("http://127.0.0.1:8000/v1/github/get_user?username=br4nch"))
            .timeout(Duration.ofSeconds(65)).GET().build();
        var response = client.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new RuntimeException("HTTP " + response.statusCode());
        System.out.println(response.body()); // Parse with your application's JSON library.
    }
}
```

## C# (.NET 6+)

```csharp
using System;
using System.Net.Http;
using System.Text.Json;

using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(65) };
using var response = await client.GetAsync("http://127.0.0.1:8000/v1/github/get_user?username=br4nch");
response.EnsureSuccessStatusCode();
using var user = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
Console.WriteLine(user.RootElement.GetProperty("login").GetString());
```

## PHP (cURL extension)

```php
<?php
$curl = curl_init('http://127.0.0.1:8000/v1/github/get_user?username=br4nch');
curl_setopt_array($curl, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 65]);
$body = curl_exec($curl);
if ($body === false) { throw new RuntimeException(curl_error($curl)); }
$status = curl_getinfo($curl, CURLINFO_HTTP_CODE);
curl_close($curl);
if ($status !== 200) { throw new RuntimeException("HTTP $status"); }
$user = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
echo $user['login'];
```

## Ruby

```ruby
require 'net/http'
require 'json'
uri = URI('http://127.0.0.1:8000/v1/github/get_user?username=br4nch')
response = Net::HTTP.start(uri.host, uri.port, read_timeout: 65) { |http| http.get(uri.request_uri) }
raise "HTTP #{response.code}" unless response.is_a?(Net::HTTPSuccess)
puts JSON.parse(response.body)['login']
```

## Generated clients

Use `http://127.0.0.1:8000/openapi.json` with an OpenAPI client generator for your
language. IDs are strings in the response schemas, and dates use ISO 8601 where
the Python model defines a datetime. These examples illustrate integration;
the automated repository tests validate the HTTP contract, not every language runtime.
