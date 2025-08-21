sequenceDiagram
    autonumber
    participant C as MCP Client (Inspector)
    participant P as Proxy / Security Checker
    participant S as Math MCP Server
    participant A as Aiceberg Risk API

    Note over C,P: STDIO JSON-RPC (one message per line)

    C->>P: tools/list (request with id)
    P->>S: forward tools/list
    S-->>P: tools list
    P-->>C: tools list

    rect rgb(245,245,245)
      C->>P: tools/call {name, arguments}
      P->>A: POST /event<br/>input="TOOL: <name>\\nARGS: {...}"
      alt Decision = allow (or flagged)
        P->>S: forward tools/call
        S-->>P: result
        P-->>C: result
      else Decision = block
        P-->>C: JSON-RPC error (-32050)<br/>"Request blocked by security policy"
      end
    end

    Note over C,P: Notifications (no <code>id</code>) are forwarded; P does not wait for a reply.