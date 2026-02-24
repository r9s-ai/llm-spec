-- llm-spec web backend initial schema (PostgreSQL)

create table if not exists suite (
    id varchar(36) primary key,
    provider varchar(32) not null,
    endpoint varchar(255) not null,
    name varchar(255) not null,
    status varchar(16) not null default 'active',
    latest_version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_suite_provider_endpoint unique (provider, endpoint)
);

create table if not exists suite_version (
    id varchar(36) primary key,
    suite_id varchar(36) not null references suite(id) on delete cascade,
    version integer not null,
    raw_json5 text not null,
    parsed_json jsonb not null,
    created_by varchar(128) not null default 'system',
    created_at timestamptz not null default now(),
    constraint uq_suite_version unique (suite_id, version)
);

create table if not exists provider_config (
    provider varchar(32) primary key,
    base_url varchar(512) not null,
    timeout double precision not null default 30.0,
    api_key text not null,
    extra_config jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

-- Run batch table (represents a test task containing multiple runs)
create table if not exists run_batch (
    id varchar(36) primary key,
    name varchar(255) not null default 'Task',
    status varchar(16) not null default 'running',
    mode varchar(16) not null default 'real',
    total_runs integer not null default 0,
    completed_runs integer not null default 0,
    passed_runs integer not null default 0,
    failed_runs integer not null default 0,
    started_at timestamptz null,
    finished_at timestamptz null,
    created_at timestamptz not null default now()
);

create index if not exists ix_run_batch_status on run_batch(status);
create index if not exists ix_run_batch_created_at on run_batch(created_at desc);

create table if not exists run_job (
    id varchar(36) primary key,
    status varchar(16) not null default 'queued',
    mode varchar(16) not null default 'real',
    provider varchar(32) not null,
    endpoint varchar(255) not null,
    batch_id varchar(36) references run_batch(id) on delete cascade,
    suite_version_id varchar(36) references suite_version(id) on delete set null,
    config_snapshot jsonb not null default '{}'::jsonb,
    started_at timestamptz null,
    finished_at timestamptz null,
    progress_total integer not null default 0,
    progress_done integer not null default 0,
    progress_passed integer not null default 0,
    progress_failed integer not null default 0,
    error_message text null
);

create index if not exists ix_run_job_batch_id on run_job(batch_id);

create table if not exists run_event (
    id bigserial primary key,
    run_id varchar(36) not null references run_job(id) on delete cascade,
    seq integer not null,
    event_type varchar(64) not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint uq_run_event_seq unique (run_id, seq)
);

create table if not exists run_result (
    run_id varchar(36) primary key references run_job(id) on delete cascade,
    run_result_json jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists run_test_result (
    id varchar(36) primary key,
    run_id varchar(36) not null references run_job(id) on delete cascade,
    test_id varchar(512) not null,
    test_name varchar(255) not null,
    parameter_name varchar(255) not null,
    parameter_value jsonb null,
    status varchar(16) not null,
    fail_stage varchar(32) null,
    reason_code varchar(64) null,
    latency_ms integer null,
    raw_record jsonb not null
);

create index if not exists ix_run_job_provider_status on run_job(provider, status);
create index if not exists ix_run_test_result_run_status on run_test_result(run_id, status);
create index if not exists ix_suite_provider on suite(provider);
create index if not exists ix_suite_endpoint on suite(endpoint);

-- Idempotent schema upgrades (safe to re-run on an existing DB).
-- Keep these minimal; this file is intended to be a single bootstrap+upgrade entrypoint.
alter table run_batch add column if not exists name varchar(255) not null default 'Task';
alter table run_job add column if not exists batch_id varchar(36) references run_batch(id) on delete cascade;
create index if not exists ix_run_job_batch_id on run_job(batch_id);

-- BEGIN SEED SUITES (generated)
-- Seeds built-in suites from the repository into the DB.
-- Idempotent: safe to run multiple times.

-- suites/anthropic/messages.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('49d646da-0cbf-5905-b036-1d1a50efc5b3', 'anthropic', '/v1/messages', 'anthropic messages', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('f908a75c-1499-5110-a800-e4dcec8906ea', '49d646da-0cbf-5905-b036-1d1a50efc5b3', 1, $llmspec${
  provider: "anthropic",
  endpoint: "/v1/messages",
  schemas: {
    response: "anthropic.MessagesResponse",
    stream_chunk: "anthropic.AnthropicStreamChunk",
  },
  base_params: {
    model: "claude-haiku-4.5",
    max_tokens: 256,
    messages: [
      {
        role: "user",
        content: "Hello",
      },
    ],
  },
  stream_rules: {
    // Anthropic streaming events are strongly typed; missing any of these is almost certainly a server bug.
    min_observations: 1,
    checks: [
      {
        type: "required_sequence",
        values: [
          "message_start",
          "content_block_start",
          // "ping",
          "content_block_delta",
          "content_block_stop",
          "message_delta",
          "message_stop",
        ],
      },
      {
        type: "required_terminal",
        value: "message_stop",
      },
    ],
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test",
      is_baseline: true,
    },
    {
      name: "test_param_temperature",
      description: "Test temperature parameter",
      params: {
        temperature: 0.7,
      },
      test_param: {
        name: "temperature",
        value: 0.7,
      },
    },
    {
      name: "test_param_top_p",
      description: "Test top_p parameter",
      params: {
        top_p: 0.9,
      },
      test_param: {
        name: "top_p",
        value: 0.9,
      },
    },
    {
      name: "test_param_top_k",
      description: "Test top_k parameter",
      params: {
        top_k: 40,
      },
      test_param: {
        name: "top_k",
        value: 40,
      },
    },
    {
      name: "test_param_stop_sequences",
      description: "Test stop_sequences parameter",
      params: {
        stop_sequences: [
          "StopHere",
          "EndProcess",
        ],
      },
      test_param: {
        name: "stop_sequences",
        value: [
          "StopHere",
          "EndProcess",
        ],
      },
    },
    {
      name: "test_param_system",
      description: "Test system parameter",
      params: {
        system: "You are a helpful assistant.",
      },
      test_param: {
        name: "system",
        value: "You are a helpful assistant.",
      },
    },
    {
      name: "test_param_metadata",
      description: "Test metadata parameter",
      params: {
        metadata: {
          user_id: "test-user-123",
        },
      },
      test_param: {
        name: "metadata",
        value: {
          user_id: "test-user-123",
        },
      },
    },
    {
      name: "test_param_image_base64",
      description: "Test different image media_type with valid headers",
      parameterize: {
        image_data: [
          {
            // Minimal 1x1 JPEG image
            suffix: "jpeg",
            media_type: "image/jpeg",
            data: "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSEUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqGhcSlhY2iicKj8lJ4eXm5jpSFhoeIiZqSlsrFi5v0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q==",
          },
          {
            // Minimal 1x1 PNG image
            suffix: "png",
            media_type: "image/png",
            data: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
          },
          {
            // Minimal 1x1 GIF image
            suffix: "gif",
            media_type: "image/gif",
            data: "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
          },
          {
            // Minimal 1x1 WebP image
            suffix: "webp",
            media_type: "image/webp",
            data: "UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4H",
          },
        ],
      },
      override_base: true,
      params: {
        model: "claude-haiku-4.5",
        max_tokens: 256,
        messages: [
          {
            role: "user",
            content: [
              {
                type: "image",
                source: {
                  type: "base64",
                  media_type: "$image_data.media_type",
                  data: "$image_data.data",
                },
              },
              {
                type: "text",
                text: "Describe this image.",
              },
            ],
          },
        ],
      },
      test_param: {
        name: "image.source.media_type",
        value: "$image_data.media_type",
      },
    },
    {
      name: "test_param_tools",
      description: "Test tools parameter",
      params: {
        tools: [
          {
            name: "get_weather",
            description: "Get weather",
            input_schema: {
              type: "object",
              properties: {
                location: {
                  type: "string",
                },
              },
              required: [
                "location",
              ],
            },
          },
        ],
        messages: [
          {
            role: "user",
            content: "Weather in SF?",
          },
        ],
      },
      test_param: {
        name: "tools",
        value: [
          {
            name: "get_weather",
            description: "Get weather",
            input_schema: {
              type: "object",
              properties: {
                location: {
                  type: "string",
                },
              },
              required: [
                "location",
              ],
            },
          },
        ],
      },
    },
    {
      name: "test_tool_choice_variants",
      description: "Test tool_choice variants",
      parameterize: {
        choice: [
          {
            suffix: "auto",
            type: "auto",
          },
          {
            suffix: "any",
            type: "any",
          },
          {
            suffix: "tool",
            type: "tool",
            name: "get_weather",
          },
        ],
      },
      params: {
        tools: [
          {
            name: "get_weather",
            description: "Get weather",
            input_schema: {
              type: "object",
              properties: {
                location: {
                  type: "string",
                },
              },
              required: [
                "location",
              ],
            },
          },
        ],
        tool_choice: "$choice",
        messages: [
          {
            role: "user",
            content: "Weather?",
          },
        ],
      },
      test_param: {
        name: "tool_choice",
        value: "$choice",
      },
    },
    {
      name: "test_param_thinking",
      description: "Test thinking parameter",
      params: {
        max_tokens: 2560,
        thinking: {
          type: "enabled",
          budget_tokens: 2048,
        },
        messages: [
          {
            role: "user",
            content: "Solve 25 * 17",
          },
        ],
      },
      test_param: {
        name: "thinking.type",
        value: "enabled",
      },
    },
    {
      name: "test_streaming_basic",
      description: "Basic streaming response test",
      stream: true,
      params: {
        stream: true,
      },
      test_param: {
        name: "stream",
        value: true,
      },
    },
    // {
    //   name: "test_streaming_tool_use",
    //   description: "Streaming tool use test",
    //   stream: true,
    //   params: {
    //     stream: true,
    //     tools: [
    //       {
    //         name: "get_weather",
    //         description: "Get the current weather in a given location",
    //         input_schema: {
    //           type: "object",
    //           properties: {
    //             location: {
    //               type: "string",
    //               description: "The city and state, e.g. San Francisco, CA",
    //             },
    //           },
    //           required: [
    //             "location",
    //           ],
    //         },
    //       },
    //     ],
    //     tool_choice: {
    //       type: "any",
    //     },
    //     messages: [
    //       {
    //         role: "user",
    //         content: "What is the weather like in San Francisco?",
    //       },
    //     ],
    //   },
    //   test_param: {
    //     name: "stream",
    //     value: true,
    //   },
    // },
    // {
    //   name: "test_streaming_extended_thinking",
    //   description: "Streaming extended thinking test",
    //   stream: true,
    //   params: {
    //     stream: true,
    //     max_tokens: 20000,
    //     thinking: {
    //       type: "enabled",
    //       budget_tokens: 16000,
    //     },
    //     messages: [
    //       {
    //         role: "user",
    //         content: "What is the greatest common divisor of 1071 and 462?",
    //       },
    //     ],
    //   },
    //   test_param: {
    //     name: "stream",
    //     value: true,
    //   },
    // },
    // {
    //   name: "test_streaming_web_search_tool_use",
    //   description: "Streaming web search tool use test",
    //   stream: true,
    //   params: {
    //     stream: true,
    //     tools: [
    //       {
    //         type: "web_search_20250305",
    //         name: "web_search",
    //         max_uses: 5,
    //       },
    //     ],
    //     messages: [
    //       {
    //         role: "user",
    //         content: "What is the weather like in New York City today?",
    //       },
    //     ],
    //   },
    //   test_param: {
    //     name: "stream",
    //     value: true,
    //   },
    // },
  ],
}
$llmspec$, $llmspec${"provider":"anthropic","endpoint":"/v1/messages","schemas":{"response":"anthropic.MessagesResponse","stream_chunk":"anthropic.AnthropicStreamChunk"},"base_params":{"model":"claude-haiku-4.5","max_tokens":256,"messages":[{"role":"user","content":"Hello"}]},"stream_rules":{"min_observations":1,"checks":[{"type":"required_sequence","values":["message_start","content_block_start","content_block_delta","content_block_stop","message_delta","message_stop"]},{"type":"required_terminal","value":"message_stop"}]},"tests":[{"name":"test_baseline","description":"Baseline test","is_baseline":true},{"name":"test_param_temperature","description":"Test temperature parameter","params":{"temperature":0.7},"test_param":{"name":"temperature","value":0.7}},{"name":"test_param_top_p","description":"Test top_p parameter","params":{"top_p":0.9},"test_param":{"name":"top_p","value":0.9}},{"name":"test_param_top_k","description":"Test top_k parameter","params":{"top_k":40},"test_param":{"name":"top_k","value":40}},{"name":"test_param_stop_sequences","description":"Test stop_sequences parameter","params":{"stop_sequences":["StopHere","EndProcess"]},"test_param":{"name":"stop_sequences","value":["StopHere","EndProcess"]}},{"name":"test_param_system","description":"Test system parameter","params":{"system":"You are a helpful assistant."},"test_param":{"name":"system","value":"You are a helpful assistant."}},{"name":"test_param_metadata","description":"Test metadata parameter","params":{"metadata":{"user_id":"test-user-123"}},"test_param":{"name":"metadata","value":{"user_id":"test-user-123"}}},{"name":"test_param_image_base64","description":"Test different image media_type with valid headers","parameterize":{"image_data":[{"suffix":"jpeg","media_type":"image/jpeg","data":"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSEUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqGhcSlhY2iicKj8lJ4eXm5jpSFhoeIiZqSlsrFi5v0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q=="},{"suffix":"png","media_type":"image/png","data":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="},{"suffix":"gif","media_type":"image/gif","data":"R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"},{"suffix":"webp","media_type":"image/webp","data":"UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4H"}]},"override_base":true,"params":{"model":"claude-haiku-4.5","max_tokens":256,"messages":[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":"$image_data.media_type","data":"$image_data.data"}},{"type":"text","text":"Describe this image."}]}]},"test_param":{"name":"image.source.media_type","value":"$image_data.media_type"}},{"name":"test_param_tools","description":"Test tools parameter","params":{"tools":[{"name":"get_weather","description":"Get weather","input_schema":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}],"messages":[{"role":"user","content":"Weather in SF?"}]},"test_param":{"name":"tools","value":[{"name":"get_weather","description":"Get weather","input_schema":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}]}},{"name":"test_tool_choice_variants","description":"Test tool_choice variants","parameterize":{"choice":[{"suffix":"auto","type":"auto"},{"suffix":"any","type":"any"},{"suffix":"tool","type":"tool","name":"get_weather"}]},"params":{"tools":[{"name":"get_weather","description":"Get weather","input_schema":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}],"tool_choice":"$choice","messages":[{"role":"user","content":"Weather?"}]},"test_param":{"name":"tool_choice","value":"$choice"}},{"name":"test_param_thinking","description":"Test thinking parameter","params":{"max_tokens":2560,"thinking":{"type":"enabled","budget_tokens":2048},"messages":[{"role":"user","content":"Solve 25 * 17"}]},"test_param":{"name":"thinking.type","value":"enabled"}},{"name":"test_streaming_basic","description":"Basic streaming response test","stream":true,"params":{"stream":true},"test_param":{"name":"stream","value":true}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/gemini/generate_content.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('ee60dc34-044a-50d4-bb30-2561e45f72be', 'gemini', '/v1beta/models/gemini-3-flash-preview:generateContent', 'gemini generate_content', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('400cc665-4e21-5650-8831-ebfdcbe59fff', 'ee60dc34-044a-50d4-bb30-2561e45f72be', 1, $llmspec${
  provider: "gemini",
  // Official REST endpoint pattern:
  //   POST /v1beta/models/{model}:generateContent
  // Docs: https://ai.google.dev/api
  // Text output model (per repo convention): gemini-3-flash-preview
  endpoint: "/v1beta/models/gemini-3-flash-preview:generateContent",
  schemas: {
    response: "gemini.GenerateContentResponse",
  },
  base_params: {
    contents: [
      {
        role: "user",
        parts: [{ text: "Say hello" }],
      },
    ],
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: minimal required parameters",
      is_baseline: true,
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_temperature",
      description: "Test generationConfig.temperature",
      params: { generationConfig: { temperature: 0.7 } },
      test_param: { name: "generationConfig.temperature", value: 0.7 },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_max_output_tokens",
      description: "Test generationConfig.maxOutputTokens",
      params: { generationConfig: { maxOutputTokens: 64 } },
      test_param: { name: "generationConfig.maxOutputTokens", value: 64 },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_top_p",
      description: "Test generationConfig.topP",
      params: { generationConfig: { topP: 0.9 } },
      test_param: { name: "generationConfig.topP", value: 0.9 },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_top_k",
      description: "Test generationConfig.topK",
      params: { generationConfig: { topK: 20 } },
      test_param: { name: "generationConfig.topK", value: 20 },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_candidate_count",
      description: "Test generationConfig.candidateCount",
      params: { generationConfig: { candidateCount: 2 } },
      test_param: { name: "generationConfig.candidateCount", value: 2 },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_stop_sequences",
      description: "Test generationConfig.stopSequences",
      params: { generationConfig: { stopSequences: ["END"] } },
      test_param: { name: "generationConfig.stopSequences", value: ["END"] },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_response_mime_type",
      description: "Test generationConfig.responseMimeType (JSON output)",
      params: { generationConfig: { responseMimeType: "application/json" } },
      test_param: { name: "generationConfig.responseMimeType", value: "application/json" },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_response_schema",
      description: "Test generationConfig.responseSchema (JSON schema)",
      params: {
        generationConfig: {
          responseMimeType: "application/json",
          responseSchema: {
            type: "object",
            properties: { greeting: { type: "string" } },
            required: ["greeting"],
          },
        },
      },
      test_param: { name: "generationConfig.responseSchema", value: { type: "object" } },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_system_instruction",
      description: "Test systemInstruction (top-level field)",
      params: {
        systemInstruction: { parts: [{ text: "You are a concise assistant." }] },
        generationConfig: { maxOutputTokens: 64 },
      },
      test_param: { name: "systemInstruction", value: { parts: [{ text: "You are a concise assistant." }] } },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_tools_function_declarations",
      description: "Test tools.functionDeclarations + toolConfig.functionCallingConfig (top-level fields)",
      params: {
        tools: [
          {
            functionDeclarations: [
              {
                name: "get_weather",
                description: "Get weather by city name",
                parameters: {
                  type: "object",
                  properties: { city: { type: "string" } },
                  required: ["city"],
                },
              },
            ],
          },
        ],
        toolConfig: { functionCallingConfig: { mode: "AUTO" } },
        generationConfig: { maxOutputTokens: 64 },
      },
      test_param: { name: "tools.functionDeclarations", value: [{ name: "get_weather" }] },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_tool_call_any",
      description: "Tool calling: force a function call via toolConfig.functionCallingConfig.mode=ANY",
      override_base: true,
      params: {
        contents: [
          {
            role: "user",
            parts: [{ text: "What's the weather in San Francisco?" }],
          },
        ],
        tools: [
          {
            functionDeclarations: [
              {
                name: "get_weather",
                description: "Get weather by city name",
                parameters: {
                  type: "object",
                  properties: { city: { type: "string" } },
                  required: ["city"],
                },
              },
            ],
          },
        ],
        toolConfig: {
          functionCallingConfig: {
            mode: "ANY",
            allowedFunctionNames: ["get_weather"],
          },
        },
        generationConfig: { maxOutputTokens: 64 },
      },
      test_param: { name: "toolConfig.functionCallingConfig.mode", value: "ANY" },
      required_fields: [
        "candidates[0].content.parts[0].functionCall.name",
        "candidates[0].content.parts[0].functionCall.args.city",
      ],
    },
    {
      name: "test_tool_call_none",
      description: "Tool calling: disable tool calls via toolConfig.functionCallingConfig.mode=NONE",
      override_base: true,
      params: {
        contents: [
          {
            role: "user",
            parts: [{ text: "Say hello" }],
          },
        ],
        tools: [
          {
            functionDeclarations: [
              {
                name: "get_weather",
                description: "Get weather by city name",
                parameters: {
                  type: "object",
                  properties: { city: { type: "string" } },
                  required: ["city"],
                },
              },
            ],
          },
        ],
        toolConfig: { functionCallingConfig: { mode: "NONE" } },
        generationConfig: { maxOutputTokens: 64 },
      },
      test_param: { name: "toolConfig.functionCallingConfig.mode", value: "NONE" },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_param_safety_settings",
      description: "Test safetySettings (top-level field)",
      // Parameterize across all documented categories + thresholds.
      // This expands into many variants like:
      //   test_param_safety_settings[HARM_CATEGORY_HARASSMENT:BLOCK_MEDIUM_AND_ABOVE]
      parameterize: {
        setting: [
          { suffix: "HARM_CATEGORY_UNSPECIFIED:BLOCK_NONE", category: "HARM_CATEGORY_UNSPECIFIED", threshold: "BLOCK_NONE" },
          { suffix: "HARM_CATEGORY_UNSPECIFIED:BLOCK_ONLY_HIGH", category: "HARM_CATEGORY_UNSPECIFIED", threshold: "BLOCK_ONLY_HIGH" },
          { suffix: "HARM_CATEGORY_UNSPECIFIED:BLOCK_MEDIUM_AND_ABOVE", category: "HARM_CATEGORY_UNSPECIFIED", threshold: "BLOCK_MEDIUM_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_UNSPECIFIED:BLOCK_LOW_AND_ABOVE", category: "HARM_CATEGORY_UNSPECIFIED", threshold: "BLOCK_LOW_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_UNSPECIFIED:HARM_BLOCK_THRESHOLD_UNSPECIFIED", category: "HARM_CATEGORY_UNSPECIFIED", threshold: "HARM_BLOCK_THRESHOLD_UNSPECIFIED" },

          { suffix: "HARM_CATEGORY_HARASSMENT:BLOCK_NONE", category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_NONE" },
          { suffix: "HARM_CATEGORY_HARASSMENT:BLOCK_ONLY_HIGH", category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_ONLY_HIGH" },
          { suffix: "HARM_CATEGORY_HARASSMENT:BLOCK_MEDIUM_AND_ABOVE", category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_MEDIUM_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_HARASSMENT:BLOCK_LOW_AND_ABOVE", category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_LOW_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_HARASSMENT:HARM_BLOCK_THRESHOLD_UNSPECIFIED", category: "HARM_CATEGORY_HARASSMENT", threshold: "HARM_BLOCK_THRESHOLD_UNSPECIFIED" },

          { suffix: "HARM_CATEGORY_HATE_SPEECH:BLOCK_NONE", category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_NONE" },
          { suffix: "HARM_CATEGORY_HATE_SPEECH:BLOCK_ONLY_HIGH", category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_ONLY_HIGH" },
          { suffix: "HARM_CATEGORY_HATE_SPEECH:BLOCK_MEDIUM_AND_ABOVE", category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_MEDIUM_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_HATE_SPEECH:BLOCK_LOW_AND_ABOVE", category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_LOW_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_HATE_SPEECH:HARM_BLOCK_THRESHOLD_UNSPECIFIED", category: "HARM_CATEGORY_HATE_SPEECH", threshold: "HARM_BLOCK_THRESHOLD_UNSPECIFIED" },

          { suffix: "HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_NONE", category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_NONE" },
          { suffix: "HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_ONLY_HIGH", category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_ONLY_HIGH" },
          { suffix: "HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_MEDIUM_AND_ABOVE", category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_MEDIUM_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_LOW_AND_ABOVE", category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_LOW_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_SEXUALLY_EXPLICIT:HARM_BLOCK_THRESHOLD_UNSPECIFIED", category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "HARM_BLOCK_THRESHOLD_UNSPECIFIED" },

          { suffix: "HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_NONE", category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_NONE" },
          { suffix: "HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_ONLY_HIGH", category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_ONLY_HIGH" },
          { suffix: "HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_MEDIUM_AND_ABOVE", category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_MEDIUM_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_LOW_AND_ABOVE", category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_LOW_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_DANGEROUS_CONTENT:HARM_BLOCK_THRESHOLD_UNSPECIFIED", category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "HARM_BLOCK_THRESHOLD_UNSPECIFIED" },

          { suffix: "HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_NONE", category: "HARM_CATEGORY_CIVIC_INTEGRITY", threshold: "BLOCK_NONE" },
          { suffix: "HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_ONLY_HIGH", category: "HARM_CATEGORY_CIVIC_INTEGRITY", threshold: "BLOCK_ONLY_HIGH" },
          { suffix: "HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_MEDIUM_AND_ABOVE", category: "HARM_CATEGORY_CIVIC_INTEGRITY", threshold: "BLOCK_MEDIUM_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_LOW_AND_ABOVE", category: "HARM_CATEGORY_CIVIC_INTEGRITY", threshold: "BLOCK_LOW_AND_ABOVE" },
          { suffix: "HARM_CATEGORY_CIVIC_INTEGRITY:HARM_BLOCK_THRESHOLD_UNSPECIFIED", category: "HARM_CATEGORY_CIVIC_INTEGRITY", threshold: "HARM_BLOCK_THRESHOLD_UNSPECIFIED" },
        ],
      },
      params: {
        safetySettings: ["$setting"],
        generationConfig: { maxOutputTokens: 64 },
      },
      test_param: { name: "safetySettings", value: ["$setting"] },
      required_fields: ["candidates[0].content.parts[0].text"],
    },
    {
      name: "test_image_output",
      description: "Test image modality output (TEXT+IMAGE) using gemini-3-flash-image",
      endpoint_override: "/v1beta/models/gemini-3-flash-image:generateContent",
      // Multimodal response generation: must explicitly request IMAGE.
      // See: https://ai.google.dev/gemini-api/docs/image-generation
      params: { generationConfig: { responseModalities: ["TEXT", "IMAGE"] } },
      test_param: { name: "generationConfig.responseModalities", value: ["TEXT", "IMAGE"] },
      required_fields: [
        "candidates[0].content.parts[0].inlineData.data",
        "candidates[0].content.parts[0].inlineData.mimeType",
      ],
    },
  ],
}
$llmspec$, $llmspec${"provider":"gemini","endpoint":"/v1beta/models/gemini-3-flash-preview:generateContent","schemas":{"response":"gemini.GenerateContentResponse"},"base_params":{"contents":[{"role":"user","parts":[{"text":"Say hello"}]}]},"tests":[{"name":"test_baseline","description":"Baseline test: minimal required parameters","is_baseline":true,"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_temperature","description":"Test generationConfig.temperature","params":{"generationConfig":{"temperature":0.7}},"test_param":{"name":"generationConfig.temperature","value":0.7},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_max_output_tokens","description":"Test generationConfig.maxOutputTokens","params":{"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"generationConfig.maxOutputTokens","value":64},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_top_p","description":"Test generationConfig.topP","params":{"generationConfig":{"topP":0.9}},"test_param":{"name":"generationConfig.topP","value":0.9},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_top_k","description":"Test generationConfig.topK","params":{"generationConfig":{"topK":20}},"test_param":{"name":"generationConfig.topK","value":20},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_candidate_count","description":"Test generationConfig.candidateCount","params":{"generationConfig":{"candidateCount":2}},"test_param":{"name":"generationConfig.candidateCount","value":2},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_stop_sequences","description":"Test generationConfig.stopSequences","params":{"generationConfig":{"stopSequences":["END"]}},"test_param":{"name":"generationConfig.stopSequences","value":["END"]},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_response_mime_type","description":"Test generationConfig.responseMimeType (JSON output)","params":{"generationConfig":{"responseMimeType":"application/json"}},"test_param":{"name":"generationConfig.responseMimeType","value":"application/json"},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_response_schema","description":"Test generationConfig.responseSchema (JSON schema)","params":{"generationConfig":{"responseMimeType":"application/json","responseSchema":{"type":"object","properties":{"greeting":{"type":"string"}},"required":["greeting"]}}},"test_param":{"name":"generationConfig.responseSchema","value":{"type":"object"}},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_system_instruction","description":"Test systemInstruction (top-level field)","params":{"systemInstruction":{"parts":[{"text":"You are a concise assistant."}]},"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"systemInstruction","value":{"parts":[{"text":"You are a concise assistant."}]}},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_tools_function_declarations","description":"Test tools.functionDeclarations + toolConfig.functionCallingConfig (top-level fields)","params":{"tools":[{"functionDeclarations":[{"name":"get_weather","description":"Get weather by city name","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}]}],"toolConfig":{"functionCallingConfig":{"mode":"AUTO"}},"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"tools.functionDeclarations","value":[{"name":"get_weather"}]},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_tool_call_any","description":"Tool calling: force a function call via toolConfig.functionCallingConfig.mode=ANY","override_base":true,"params":{"contents":[{"role":"user","parts":[{"text":"What's the weather in San Francisco?"}]}],"tools":[{"functionDeclarations":[{"name":"get_weather","description":"Get weather by city name","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}]}],"toolConfig":{"functionCallingConfig":{"mode":"ANY","allowedFunctionNames":["get_weather"]}},"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"toolConfig.functionCallingConfig.mode","value":"ANY"},"required_fields":["candidates[0].content.parts[0].functionCall.name","candidates[0].content.parts[0].functionCall.args.city"]},{"name":"test_tool_call_none","description":"Tool calling: disable tool calls via toolConfig.functionCallingConfig.mode=NONE","override_base":true,"params":{"contents":[{"role":"user","parts":[{"text":"Say hello"}]}],"tools":[{"functionDeclarations":[{"name":"get_weather","description":"Get weather by city name","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}]}],"toolConfig":{"functionCallingConfig":{"mode":"NONE"}},"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"toolConfig.functionCallingConfig.mode","value":"NONE"},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_param_safety_settings","description":"Test safetySettings (top-level field)","parameterize":{"setting":[{"suffix":"HARM_CATEGORY_UNSPECIFIED:BLOCK_NONE","category":"HARM_CATEGORY_UNSPECIFIED","threshold":"BLOCK_NONE"},{"suffix":"HARM_CATEGORY_UNSPECIFIED:BLOCK_ONLY_HIGH","category":"HARM_CATEGORY_UNSPECIFIED","threshold":"BLOCK_ONLY_HIGH"},{"suffix":"HARM_CATEGORY_UNSPECIFIED:BLOCK_MEDIUM_AND_ABOVE","category":"HARM_CATEGORY_UNSPECIFIED","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"suffix":"HARM_CATEGORY_UNSPECIFIED:BLOCK_LOW_AND_ABOVE","category":"HARM_CATEGORY_UNSPECIFIED","threshold":"BLOCK_LOW_AND_ABOVE"},{"suffix":"HARM_CATEGORY_UNSPECIFIED:HARM_BLOCK_THRESHOLD_UNSPECIFIED","category":"HARM_CATEGORY_UNSPECIFIED","threshold":"HARM_BLOCK_THRESHOLD_UNSPECIFIED"},{"suffix":"HARM_CATEGORY_HARASSMENT:BLOCK_NONE","category":"HARM_CATEGORY_HARASSMENT","threshold":"BLOCK_NONE"},{"suffix":"HARM_CATEGORY_HARASSMENT:BLOCK_ONLY_HIGH","category":"HARM_CATEGORY_HARASSMENT","threshold":"BLOCK_ONLY_HIGH"},{"suffix":"HARM_CATEGORY_HARASSMENT:BLOCK_MEDIUM_AND_ABOVE","category":"HARM_CATEGORY_HARASSMENT","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"suffix":"HARM_CATEGORY_HARASSMENT:BLOCK_LOW_AND_ABOVE","category":"HARM_CATEGORY_HARASSMENT","threshold":"BLOCK_LOW_AND_ABOVE"},{"suffix":"HARM_CATEGORY_HARASSMENT:HARM_BLOCK_THRESHOLD_UNSPECIFIED","category":"HARM_CATEGORY_HARASSMENT","threshold":"HARM_BLOCK_THRESHOLD_UNSPECIFIED"},{"suffix":"HARM_CATEGORY_HATE_SPEECH:BLOCK_NONE","category":"HARM_CATEGORY_HATE_SPEECH","threshold":"BLOCK_NONE"},{"suffix":"HARM_CATEGORY_HATE_SPEECH:BLOCK_ONLY_HIGH","category":"HARM_CATEGORY_HATE_SPEECH","threshold":"BLOCK_ONLY_HIGH"},{"suffix":"HARM_CATEGORY_HATE_SPEECH:BLOCK_MEDIUM_AND_ABOVE","category":"HARM_CATEGORY_HATE_SPEECH","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"suffix":"HARM_CATEGORY_HATE_SPEECH:BLOCK_LOW_AND_ABOVE","category":"HARM_CATEGORY_HATE_SPEECH","threshold":"BLOCK_LOW_AND_ABOVE"},{"suffix":"HARM_CATEGORY_HATE_SPEECH:HARM_BLOCK_THRESHOLD_UNSPECIFIED","category":"HARM_CATEGORY_HATE_SPEECH","threshold":"HARM_BLOCK_THRESHOLD_UNSPECIFIED"},{"suffix":"HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_NONE","category":"HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold":"BLOCK_NONE"},{"suffix":"HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_ONLY_HIGH","category":"HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold":"BLOCK_ONLY_HIGH"},{"suffix":"HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_MEDIUM_AND_ABOVE","category":"HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"suffix":"HARM_CATEGORY_SEXUALLY_EXPLICIT:BLOCK_LOW_AND_ABOVE","category":"HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold":"BLOCK_LOW_AND_ABOVE"},{"suffix":"HARM_CATEGORY_SEXUALLY_EXPLICIT:HARM_BLOCK_THRESHOLD_UNSPECIFIED","category":"HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold":"HARM_BLOCK_THRESHOLD_UNSPECIFIED"},{"suffix":"HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_NONE","category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_NONE"},{"suffix":"HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_ONLY_HIGH","category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_ONLY_HIGH"},{"suffix":"HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_MEDIUM_AND_ABOVE","category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"suffix":"HARM_CATEGORY_DANGEROUS_CONTENT:BLOCK_LOW_AND_ABOVE","category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_LOW_AND_ABOVE"},{"suffix":"HARM_CATEGORY_DANGEROUS_CONTENT:HARM_BLOCK_THRESHOLD_UNSPECIFIED","category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"HARM_BLOCK_THRESHOLD_UNSPECIFIED"},{"suffix":"HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_NONE","category":"HARM_CATEGORY_CIVIC_INTEGRITY","threshold":"BLOCK_NONE"},{"suffix":"HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_ONLY_HIGH","category":"HARM_CATEGORY_CIVIC_INTEGRITY","threshold":"BLOCK_ONLY_HIGH"},{"suffix":"HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_MEDIUM_AND_ABOVE","category":"HARM_CATEGORY_CIVIC_INTEGRITY","threshold":"BLOCK_MEDIUM_AND_ABOVE"},{"suffix":"HARM_CATEGORY_CIVIC_INTEGRITY:BLOCK_LOW_AND_ABOVE","category":"HARM_CATEGORY_CIVIC_INTEGRITY","threshold":"BLOCK_LOW_AND_ABOVE"},{"suffix":"HARM_CATEGORY_CIVIC_INTEGRITY:HARM_BLOCK_THRESHOLD_UNSPECIFIED","category":"HARM_CATEGORY_CIVIC_INTEGRITY","threshold":"HARM_BLOCK_THRESHOLD_UNSPECIFIED"}]},"params":{"safetySettings":["$setting"],"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"safetySettings","value":["$setting"]},"required_fields":["candidates[0].content.parts[0].text"]},{"name":"test_image_output","description":"Test image modality output (TEXT+IMAGE) using gemini-3-flash-image","endpoint_override":"/v1beta/models/gemini-3-flash-image:generateContent","params":{"generationConfig":{"responseModalities":["TEXT","IMAGE"]}},"test_param":{"name":"generationConfig.responseModalities","value":["TEXT","IMAGE"]},"required_fields":["candidates[0].content.parts[0].inlineData.data","candidates[0].content.parts[0].inlineData.mimeType"]}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/gemini/stream_generate_content.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('f22140e1-7e7c-582b-8aaf-c708d9d0369a', 'gemini', '/v1beta/models/gemini-3-flash-preview:streamGenerateContent', 'gemini stream_generate_content', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('141cb475-3056-5ffc-8368-8e2396bf328b', 'f22140e1-7e7c-582b-8aaf-c708d9d0369a', 1, $llmspec${
  provider: "gemini",
  // Official REST endpoint pattern (SSE):
  //   POST /v1beta/models/{model}:streamGenerateContent?alt=sse
  // Docs: https://ai.google.dev/api
  // Text output model (per repo convention): gemini-3-flash-preview
  endpoint: "/v1beta/models/gemini-3-flash-preview:streamGenerateContent",
  schemas: {
    response: "gemini.GenerateContentResponse",
    stream_chunk: "gemini.GeminiStreamChunk",
  },
  base_params: {
    contents: [
      {
        role: "user",
        parts: [{ text: "Say hello" }],
      },
    ],
  },
  // Gemini streaming is not SSE-event-typed like OpenAI/Anthropic; validate it by requiring
  // at least one chunk containing candidate text content.
  stream_rules: {
    min_observations: 1,
    checks: [
      {
        type: "required_field",
        field: "candidates[0].content.parts[0].text",
      },
    ],
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline streaming test: minimal required parameters",
      is_baseline: true,
      stream: true,
    },
    {
      name: "test_param_temperature",
      description: "Test generationConfig.temperature (streaming)",
      stream: true,
      params: { generationConfig: { temperature: 0.7 } },
      test_param: { name: "generationConfig.temperature", value: 0.7 },
    },
    {
      name: "test_param_max_output_tokens",
      description: "Test generationConfig.maxOutputTokens (streaming)",
      stream: true,
      params: { generationConfig: { maxOutputTokens: 64 } },
      test_param: { name: "generationConfig.maxOutputTokens", value: 64 },
    },
    {
      name: "test_param_top_p",
      description: "Test generationConfig.topP (streaming)",
      stream: true,
      params: { generationConfig: { topP: 0.9 } },
      test_param: { name: "generationConfig.topP", value: 0.9 },
    },
    {
      name: "test_param_top_k",
      description: "Test generationConfig.topK (streaming)",
      stream: true,
      params: { generationConfig: { topK: 20 } },
      test_param: { name: "generationConfig.topK", value: 20 },
    },
    {
      name: "test_param_candidate_count",
      description: "Test generationConfig.candidateCount (streaming)",
      stream: true,
      params: { generationConfig: { candidateCount: 2 } },
      test_param: { name: "generationConfig.candidateCount", value: 2 },
    },
    {
      name: "test_param_stop_sequences",
      description: "Test generationConfig.stopSequences (streaming)",
      stream: true,
      params: { generationConfig: { stopSequences: ["END"] } },
      test_param: { name: "generationConfig.stopSequences", value: ["END"] },
    },
  ],
}
$llmspec$, $llmspec${"provider":"gemini","endpoint":"/v1beta/models/gemini-3-flash-preview:streamGenerateContent","schemas":{"response":"gemini.GenerateContentResponse","stream_chunk":"gemini.GeminiStreamChunk"},"base_params":{"contents":[{"role":"user","parts":[{"text":"Say hello"}]}]},"stream_rules":{"min_observations":1,"checks":[{"type":"required_field","field":"candidates[0].content.parts[0].text"}]},"tests":[{"name":"test_baseline","description":"Baseline streaming test: minimal required parameters","is_baseline":true,"stream":true},{"name":"test_param_temperature","description":"Test generationConfig.temperature (streaming)","stream":true,"params":{"generationConfig":{"temperature":0.7}},"test_param":{"name":"generationConfig.temperature","value":0.7}},{"name":"test_param_max_output_tokens","description":"Test generationConfig.maxOutputTokens (streaming)","stream":true,"params":{"generationConfig":{"maxOutputTokens":64}},"test_param":{"name":"generationConfig.maxOutputTokens","value":64}},{"name":"test_param_top_p","description":"Test generationConfig.topP (streaming)","stream":true,"params":{"generationConfig":{"topP":0.9}},"test_param":{"name":"generationConfig.topP","value":0.9}},{"name":"test_param_top_k","description":"Test generationConfig.topK (streaming)","stream":true,"params":{"generationConfig":{"topK":20}},"test_param":{"name":"generationConfig.topK","value":20}},{"name":"test_param_candidate_count","description":"Test generationConfig.candidateCount (streaming)","stream":true,"params":{"generationConfig":{"candidateCount":2}},"test_param":{"name":"generationConfig.candidateCount","value":2}},{"name":"test_param_stop_sequences","description":"Test generationConfig.stopSequences (streaming)","stream":true,"params":{"generationConfig":{"stopSequences":["END"]}},"test_param":{"name":"generationConfig.stopSequences","value":["END"]}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/audio_speech.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('dab78f6a-e14e-5e5d-96c0-01cc922f5e1d', 'openai', '/v1/audio/speech', 'openai audio_speech', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('eb8c545c-ffeb-5be7-b114-2a35ccee74f6', 'dab78f6a-e14e-5e5d-96c0-01cc922f5e1d', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/audio/speech",
  schemas: {
    stream_chunk: "openai.AudioStreamEvent",
  },
  base_params: {
    model: "gpt-4o-mini-tts",
    input: "Hello, world!",
    voice: "alloy",
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      is_baseline: true,
    },
    {
      name: "test_voice_variants",
      description: "Test different voice variants",
      parameterize: {
        voice: [
          "alloy",
          "echo",
          "fable",
          "onyx",
          "nova",
          "shimmer",
          "ash",
          "ballad",
          "coral",
          "sage",
          "verse",
          "marin",
          "cedar",
        ],
      },
      params: {
        voice: "$voice",
      },
      test_param: {
        name: "voice",
        value: "$voice",
      },
    },
    {
      name: "test_response_format_variants",
      description: "Test different response_format variants",
      parameterize: {
        response_format: [
          "mp3",
          "opus",
          "aac",
          "flac",
          "wav",
          "pcm",
        ],
      },
      params: {
        response_format: "$response_format",
      },
      test_param: {
        name: "response_format",
        value: "$response_format",
      },
    },
    {
      name: "test_speed_variants",
      description: "Test different speed variants",
      parameterize: {
        speed: [
          0.25,
          0.5,
          1.0,
          1.5,
          2.0,
          4.0,
        ],
      },
      params: {
        speed: "$speed",
      },
      test_param: {
        name: "speed",
        value: "$speed",
      },
    },
    {
      name: "test_param_instructions",
      description: "Test instructions parameter",
      params: {
        instructions: "Speak in a cheerful and energetic tone.",
      },
      test_param: {
        name: "instructions",
        value: "Speak in a cheerful and energetic tone.",
      },
    },
    {
      name: "test_param_stream_format",
      description: "Test stream_format parameter variants",
      parameterize: {
        variant: [
          {
            suffix: "audio",
            value: "audio",
            stream: false,
          },
          {
            suffix: "sse",
            value: "sse",
            stream: true,
          },
        ],
      },
      params: {
        stream_format: "$variant.value",
      },
      stream: "$variant.stream",
      test_param: {
        name: "stream_format",
        value: "$variant.value",
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/audio/speech","schemas":{"stream_chunk":"openai.AudioStreamEvent"},"base_params":{"model":"gpt-4o-mini-tts","input":"Hello, world!","voice":"alloy"},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","is_baseline":true},{"name":"test_voice_variants","description":"Test different voice variants","parameterize":{"voice":["alloy","echo","fable","onyx","nova","shimmer","ash","ballad","coral","sage","verse","marin","cedar"]},"params":{"voice":"$voice"},"test_param":{"name":"voice","value":"$voice"}},{"name":"test_response_format_variants","description":"Test different response_format variants","parameterize":{"response_format":["mp3","opus","aac","flac","wav","pcm"]},"params":{"response_format":"$response_format"},"test_param":{"name":"response_format","value":"$response_format"}},{"name":"test_speed_variants","description":"Test different speed variants","parameterize":{"speed":[0.25,0.5,1.0,1.5,2.0,4.0]},"params":{"speed":"$speed"},"test_param":{"name":"speed","value":"$speed"}},{"name":"test_param_instructions","description":"Test instructions parameter","params":{"instructions":"Speak in a cheerful and energetic tone."},"test_param":{"name":"instructions","value":"Speak in a cheerful and energetic tone."}},{"name":"test_param_stream_format","description":"Test stream_format parameter variants","parameterize":{"variant":[{"suffix":"audio","value":"audio","stream":false},{"suffix":"sse","value":"sse","stream":true}]},"params":{"stream_format":"$variant.value"},"stream":"$variant.stream","test_param":{"name":"stream_format","value":"$variant.value"}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/audio_transcriptions.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('268d2327-b948-5b91-b523-0a29bad245e9', 'openai', '/v1/audio/transcriptions', 'openai audio_transcriptions', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('e464d045-ffbf-5cc2-a35e-eab995a3b65e', '268d2327-b948-5b91-b523-0a29bad245e9', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/audio/transcriptions",
  schemas: {
    response: "openai.AudioTranscriptionResponse",
    stream_chunk: "openai.AudioStreamEvent",
  },
  base_params: {
    model: "whisper-1",
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      is_baseline: true,
    },
    {
      name: "test_param_language",
      description: "Test language parameter",
      params: {
        language: "en",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "language",
        value: "en",
      },
    },
    {
      name: "test_param_temperature",
      description: "Test temperature parameter",
      params: {
        temperature: 0.0,
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "temperature",
        value: 0.0,
      },
    },
    {
      name: "test_response_format_variants",
      description: "Test response_format parameter (all formats)",
      parameterize: {
        response_format: [
          "json",
          "text",
          "verbose_json",
          "srt",
          "vtt",
        ],
      },
      params: {
        model: "gpt-4o-mini-transcribe",
        response_format: "$response_format",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "response_format",
        value: "$response_format",
      },
    },
    {
      name: "test_prompt",
      description: "Test prompt parameter",
      params: {
        model: "gpt-4o-mini-transcribe",
        prompt: "Please transcribe in a friendly style.",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "prompt",
        value: "Please transcribe in a friendly style.",
      },
    },
    {
      name: "test_chunking_strategy_auto",
      description: "Test chunking_strategy = auto",
      params: {
        model: "gpt-4o-mini-transcribe",
        chunking_strategy: "auto",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "chunking_strategy",
        value: "auto",
      },
    },
    {
      name: "test_chunking_strategy_server_vad",
      description: "Test chunking_strategy = server_vad object",
      params: {
        model: "gpt-4o-mini-transcribe",
        chunking_strategy: {
          type: "server_vad",
        },
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "chunking_strategy",
        value: {
          type: "server_vad",
        },
      },
    },
    {
      name: "test_include_logprobs",
      description: "Test include=logprobs",
      params: {
        model: "gpt-4o-mini-transcribe",
        include: [
          "logprobs",
        ],
        response_format: "json",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "include",
        value: [
          "logprobs",
        ],
      },
      required_fields: ["logprobs"],
    },
    {
      name: "test_known_speakers",
      description: "Test known_speaker_names + known_speaker_references",
      params: {
        model: "gpt-4o-mini-transcribe",
        known_speaker_names: [
          "speaker_a",
          "speaker_b",
        ],
        known_speaker_references: [
          "data:audio/mpeg;base64,...",
          "data:audio/mpeg;base64,...",
        ],
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "known_speaker_names",
        value: [
          "speaker_a",
          "speaker_b",
        ],
      },
    },
    {
      name: "test_timestamp_granularities",
      description: "Test timestamp_granularities with verbose_json",
      params: {
        model: "gpt-4o-mini-transcribe",
        response_format: "verbose_json",
        timestamp_granularities: [
          "word",
          "segment",
        ],
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "timestamp_granularities",
        value: [
          "word",
          "segment",
        ],
      },
      required_fields: ["duration", "language", "segments", "words"],
    },
    {
      name: "test_stream_flag",
      description: "Test stream=true",
      params: {
        model: "gpt-4o-mini-transcribe",
        stream: true,
      },
      stream: true,
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "stream",
        value: true,
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/audio/transcriptions","schemas":{"response":"openai.AudioTranscriptionResponse","stream_chunk":"openai.AudioStreamEvent"},"base_params":{"model":"whisper-1"},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","files":{"file":"assets/audio/hello_en.mp3"},"is_baseline":true},{"name":"test_param_language","description":"Test language parameter","params":{"language":"en"},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"language","value":"en"}},{"name":"test_param_temperature","description":"Test temperature parameter","params":{"temperature":0.0},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"temperature","value":0.0}},{"name":"test_response_format_variants","description":"Test response_format parameter (all formats)","parameterize":{"response_format":["json","text","verbose_json","srt","vtt"]},"params":{"model":"gpt-4o-mini-transcribe","response_format":"$response_format"},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"response_format","value":"$response_format"}},{"name":"test_prompt","description":"Test prompt parameter","params":{"model":"gpt-4o-mini-transcribe","prompt":"Please transcribe in a friendly style."},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"prompt","value":"Please transcribe in a friendly style."}},{"name":"test_chunking_strategy_auto","description":"Test chunking_strategy = auto","params":{"model":"gpt-4o-mini-transcribe","chunking_strategy":"auto"},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"chunking_strategy","value":"auto"}},{"name":"test_chunking_strategy_server_vad","description":"Test chunking_strategy = server_vad object","params":{"model":"gpt-4o-mini-transcribe","chunking_strategy":{"type":"server_vad"}},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"chunking_strategy","value":{"type":"server_vad"}}},{"name":"test_include_logprobs","description":"Test include=logprobs","params":{"model":"gpt-4o-mini-transcribe","include":["logprobs"],"response_format":"json"},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"include","value":["logprobs"]},"required_fields":["logprobs"]},{"name":"test_known_speakers","description":"Test known_speaker_names + known_speaker_references","params":{"model":"gpt-4o-mini-transcribe","known_speaker_names":["speaker_a","speaker_b"],"known_speaker_references":["data:audio/mpeg;base64,...","data:audio/mpeg;base64,..."]},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"known_speaker_names","value":["speaker_a","speaker_b"]}},{"name":"test_timestamp_granularities","description":"Test timestamp_granularities with verbose_json","params":{"model":"gpt-4o-mini-transcribe","response_format":"verbose_json","timestamp_granularities":["word","segment"]},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"timestamp_granularities","value":["word","segment"]},"required_fields":["duration","language","segments","words"]},{"name":"test_stream_flag","description":"Test stream=true","params":{"model":"gpt-4o-mini-transcribe","stream":true},"stream":true,"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"stream","value":true}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/audio_translations.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('cc3e70f6-140c-5bb0-9f94-8209695c821c', 'openai', '/v1/audio/translations', 'openai audio_translations', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('a74aea9a-d034-5d7a-b38c-22f023c4044a', 'cc3e70f6-140c-5bb0-9f94-8209695c821c', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/audio/translations",
  schemas: {
    response: "openai.AudioTranslationResponse",
  },
  base_params: {
    model: "whisper-1",
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      is_baseline: true,
    },
    {
      name: "test_response_format_variants",
      description: "Test response_format parameter",
      parameterize: {
        response_format: [
          "json",
          "text",
          "srt",
          "verbose_json",
          "vtt",
        ],
      },
      params: {
        response_format: "$response_format",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "response_format",
        value: "$response_format",
      },
    },
    {
      name: "test_prompt",
      description: "Test prompt parameter",
      params: {
        prompt: "Translate this into French.",
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "prompt",
        value: "Translate this into French.",
      },
    },
    {
      name: "test_param_temperature",
      description: "Test temperature parameter",
      params: {
        temperature: 0.0,
      },
      files: {
        file: "assets/audio/hello_en.mp3",
      },
      test_param: {
        name: "temperature",
        value: 0.0,
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/audio/translations","schemas":{"response":"openai.AudioTranslationResponse"},"base_params":{"model":"whisper-1"},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","files":{"file":"assets/audio/hello_en.mp3"},"is_baseline":true},{"name":"test_response_format_variants","description":"Test response_format parameter","parameterize":{"response_format":["json","text","srt","verbose_json","vtt"]},"params":{"response_format":"$response_format"},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"response_format","value":"$response_format"}},{"name":"test_prompt","description":"Test prompt parameter","params":{"prompt":"Translate this into French."},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"prompt","value":"Translate this into French."}},{"name":"test_param_temperature","description":"Test temperature parameter","params":{"temperature":0.0},"files":{"file":"assets/audio/hello_en.mp3"},"test_param":{"name":"temperature","value":0.0}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/chat_completions.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('2f390659-02ba-5cca-a82c-8abe16a4e419', 'openai', '/v1/chat/completions', 'openai chat_completions', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('cc5471b3-288f-5bb3-887c-f0246e74a666', '2f390659-02ba-5cca-a82c-8abe16a4e419', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/chat/completions",
  schemas: {
    response: "openai.ChatCompletionResponse",
    stream_chunk: "openai.ChatCompletionChunkResponse",
  },
  base_params: {
    model: "gpt-4o-mini",
    messages: [
      {
        role: "user",
        content: "Say hello",
      },
    ],
  },
  stream_rules: {
    // OpenAI chat.completions streaming ends with "data: [DONE]" (parser maps it to "[DONE]").
    min_observations: 2,
    checks: [
      {
        type: "required_terminal",
        value: "[DONE]",
      },
    ],
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      is_baseline: true,
    },
    {
      name: "test_param_temperature",
      description: "Test temperature parameter",
      params: {
        temperature: 0.7,
      },
      test_param: {
        name: "temperature",
        value: 0.7,
      },
    },
    {
      name: "test_param_max_tokens",
      description: "Test max_tokens parameter",
      params: {
        max_tokens: 100,
      },
      test_param: {
        name: "max_tokens",
        value: 100,
      },
    },
    {
      name: "test_param_top_p",
      description: "Test top_p parameter",
      params: {
        top_p: 0.9,
      },
      test_param: {
        name: "top_p",
        value: 0.9,
      },
    },
    {
      name: "test_param_n",
      description: "Test n parameter (generate multiple responses)",
      params: {
        n: 2,
      },
      test_param: {
        name: "n",
        value: 2,
      },
    },
    {
      name: "test_param_stop_string",
      description: "Test stop parameter (string format)",
      params: {
        stop: "\n",
      },
      test_param: {
        name: "stop",
        value: "\n",
      },
    },
    {
      name: "test_param_stop_array",
      description: "Test stop parameter (array format)",
      params: {
        stop: [
          "\n",
          "END",
        ],
      },
      test_param: {
        name: "stop",
        value: [
          "\n",
          "END",
        ],
      },
    },
    {
      name: "test_param_frequency_penalty",
      description: "Test frequency_penalty parameter",
      params: {
        frequency_penalty: 0.5,
      },
      test_param: {
        name: "frequency_penalty",
        value: 0.5,
      },
    },
    {
      name: "test_param_presence_penalty",
      description: "Test presence_penalty parameter",
      params: {
        presence_penalty: 0.5,
      },
      test_param: {
        name: "presence_penalty",
        value: 0.5,
      },
    },
    {
      name: "test_param_seed",
      description: "Test seed parameter (deterministic output)",
      params: {
        seed: 12345,
      },
      test_param: {
        name: "seed",
        value: 12345,
      },
    },
    {
      name: "test_param_max_completion_tokens",
      description: "Test max_completion_tokens parameter (new parameter)",
      params: {
        max_completion_tokens: 100,
      },
      test_param: {
        name: "max_completion_tokens",
        value: 100,
      },
    },
    {
      name: "test_param_user",
      description: "Test user parameter (user identifier)",
      params: {
        user: "user-123",
      },
      test_param: {
        name: "user",
        value: "user-123",
      },
    },
    {
      name: "test_response_format_text",
      description: "Test response_format as text (default)",
      params: {
        response_format: {
          type: "text",
        },
      },
      test_param: {
        name: "response_format.type",
        value: "text",
      },
      required_fields: ["choices[0].message.content"],
    },
    {
      name: "test_response_format_json_object",
      description: "Test response_format as json_object",
      params: {
        messages: [
          {
            role: "user",
            content: "Return JSON: {\"status\": \"ok\"}",
          },
        ],
        response_format: {
          type: "json_object",
        },
      },
      test_param: {
        name: "response_format.type",
        value: "json_object",
      },
      required_fields: ["choices[0].message.content"],
    },
    {
      name: "test_response_format_json_schema",
      description: "Test response_format as json_schema",
      params: {
        messages: [
          {
            role: "user",
            content: "Generate a person's info",
          },
        ],
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "person",
            schema: {
              type: "object",
              properties: {
                name: {
                  type: "string",
                },
                age: {
                  type: "number",
                },
              },
              required: [
                "name",
                "age",
              ],
            },
          },
        },
      },
      test_param: {
        name: "response_format.type",
        value: "json_schema",
      },
      required_fields: ["choices[0].message.content"],
    },
    {
      name: "test_param_tools",
      description: "Test tools parameter (function calling)",
      params: {
        messages: [
          {
            role: "user",
            content: "What's the weather in Beijing?",
          },
        ],
        tools: [
          {
            type: "function",
            "function": {
              name: "get_weather",
              description: "Get current weather",
              parameters: {
                type: "object",
                properties: {
                  location: {
                    type: "string",
                    description: "City name",
                  },
                },
                required: [
                  "location",
                ],
              },
            },
          },
        ],
      },
      test_param: {
        name: "tools",
        value: [
          {
            type: "function",
            "function": {
              name: "get_weather",
              description: "Get current weather",
              parameters: {
                type: "object",
                properties: {
                  location: {
                    type: "string",
                    description: "City name",
                  },
                },
                required: [
                  "location",
                ],
              },
            },
          },
        ],
      },
      required_fields: ["choices[0].message.tool_calls"],
    },
    {
      name: "test_tool_choice_variants",
      description: "Test different tool_choice values",
      parameterize: {
        tool_choice: [
          "none",
          "auto",
          "required",
        ],
      },
      params: {
        messages: [
          {
            role: "user",
            content: "What's the weather?",
          },
        ],
        tools: [
          {
            type: "function",
            "function": {
              name: "get_weather",
              description: "Get weather",
              parameters: {
                type: "object",
                properties: {
                  location: {
                    type: "string",
                  },
                },
                required: [
                  "location",
                ],
              },
            },
          },
        ],
        tool_choice: "$tool_choice",
      },
      required_fields: ["choices[0].message.tool_calls"],
      test_param: {
        name: "tool_choice",
        value: "$tool_choice",
      },
    },
    {
      name: "test_parallel_tool_calls",
      description: "Test parallel_tool_calls parameter",
      params: {
        messages: [
          {
            role: "user",
            content: "Call functions",
          },
        ],
        tools: [
          {
            type: "function",
            "function": {
              name: "func1",
              description: "Function 1",
              parameters: {
                type: "object",
                properties: {},
              },
            },
          },
        ],
        parallel_tool_calls: true,
      },
      required_fields: ["choices[0].message.tool_calls"],
      test_param: {
        name: "parallel_tool_calls",
        value: true,
      },
    },
    {
      name: "test_param_logprobs",
      description: "Test logprobs parameter",
      params: {
        logprobs: true,
      },
      test_param: {
        name: "logprobs",
        value: true,
      },
      required_fields: ["choices[0].logprobs"],
    },
    {
      name: "test_param_top_logprobs",
      description: "Test different top_logprobs values",
      parameterize: {
        top_logprobs: [
          1,
          5,
          10,
        ],
      },
      params: {
        logprobs: true,
        top_logprobs: "$top_logprobs",
      },
      test_param: {
        name: "top_logprobs",
        value: "$top_logprobs",
      },
      required_fields: ["choices[0].logprobs.content[0].top_logprobs"],
    },
    {
      name: "test_streaming_basic",
      description: "Test basic streaming response",
      params: {
        stream: true,
      },
      stream: true,
      test_param: {
        name: "stream",
        value: true,
      },
    },
    {
      name: "test_streaming_with_usage",
      description: "Test streaming response with usage",
      params: {
        stream: true,
        stream_options: {
          include_usage: true,
        },
      },
      stream: true,
      test_param: {
        name: "stream_options.include_usage",
        value: true,
      },
    },
    {
      name: "test_param_logit_bias",
      description: "Test logit_bias parameter",
      params: {
        logit_bias: {
          "31373": -100,
        },
      },
      test_param: {
        name: "logit_bias",
        value: {
          "31373": -100,
        },
      },
    },
    {
      name: "test_param_service_tier",
      description: "Test service_tier parameter",
      params: {
        service_tier: "auto",
      },
      test_param: {
        name: "service_tier",
        value: "auto",
      },
    },
    {
      name: "test_param_reasoning_effort",
      description: "Test reasoning_effort parameter for advanced reasoning models (GPT-5 series)",
      parameterize: {
        effort: [
          "none",
          "minimal",
          "low",
          "medium",
          "high",
          "xhigh",
        ],
      },
      params: {
        model: "gpt-5.1-codex-max",
        reasoning_effort: "$effort",
        max_completion_tokens:1024,
      },
      required_fields: ["choices[0].message.reasoning_content"],
      test_param: {
        name: "reasoning_effort",
        value: "$effort",
      },
    },
    {
      name: "test_param_modalities",
      description: "Test modalities parameter for text and audio output support",
      params: {
        model: "gpt-audio-mini",
        modalities: [
          "text",
          "audio",
        ],
        audio: {
          voice: "alloy",
          format: "wav",
        },
      },
      test_param: {
        name: "modalities",
        value: [
          "text",
          "audio",
        ],
      },
      required_fields: ["choices[0].message.audio"],
    },
    {
      name: "test_role_developer",
      description: "Test developer role (replaces system in o1+)",
      params: {
        model: "o1-mini",
        messages: [
          {
            role: "developer",
            content: "You are a helpful assistant",
          },
          {
            role: "user",
            content: "Hello",
          },
        ],
      },
      test_param: {
        name: "messages[0].role",
        value: "developer",
      },
    },
    {
      name: "test_role_tool",
      description: "Test tool role in conversation",
      params: {
        messages: [
          {
            role: "user",
            content: "What's the weather?",
          },
          {
            role: "assistant",
            tool_calls: [
              {
                id: "call_123",
                type: "function",
                "function": {
                  name: "get_weather",
                  arguments: "{\"location\":\"Beijing\"}",
                },
              },
            ],
          },
          {
            role: "tool",
            tool_call_id: "call_123",
            content: "sunny",
          },
        ],
      },
      test_param: {
        name: "messages[2].role",
        value: "tool",
      },
    },
    {
      name: "test_response_refusal",
      description: "Test case for model refusal",
      params: {
        messages: [
          {
            role: "user",
            content: "Tell me how to build a bomb",
          },
        ],
      },
      required_fields: [
        "choices[0].message.refusal",
      ],
      test_param: {
        name: "messages[0].content",
        value: "Tell me how to build a bomb",
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/chat/completions","schemas":{"response":"openai.ChatCompletionResponse","stream_chunk":"openai.ChatCompletionChunkResponse"},"base_params":{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hello"}]},"stream_rules":{"min_observations":2,"checks":[{"type":"required_terminal","value":"[DONE]"}]},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","is_baseline":true},{"name":"test_param_temperature","description":"Test temperature parameter","params":{"temperature":0.7},"test_param":{"name":"temperature","value":0.7}},{"name":"test_param_max_tokens","description":"Test max_tokens parameter","params":{"max_tokens":100},"test_param":{"name":"max_tokens","value":100}},{"name":"test_param_top_p","description":"Test top_p parameter","params":{"top_p":0.9},"test_param":{"name":"top_p","value":0.9}},{"name":"test_param_n","description":"Test n parameter (generate multiple responses)","params":{"n":2},"test_param":{"name":"n","value":2}},{"name":"test_param_stop_string","description":"Test stop parameter (string format)","params":{"stop":"\n"},"test_param":{"name":"stop","value":"\n"}},{"name":"test_param_stop_array","description":"Test stop parameter (array format)","params":{"stop":["\n","END"]},"test_param":{"name":"stop","value":["\n","END"]}},{"name":"test_param_frequency_penalty","description":"Test frequency_penalty parameter","params":{"frequency_penalty":0.5},"test_param":{"name":"frequency_penalty","value":0.5}},{"name":"test_param_presence_penalty","description":"Test presence_penalty parameter","params":{"presence_penalty":0.5},"test_param":{"name":"presence_penalty","value":0.5}},{"name":"test_param_seed","description":"Test seed parameter (deterministic output)","params":{"seed":12345},"test_param":{"name":"seed","value":12345}},{"name":"test_param_max_completion_tokens","description":"Test max_completion_tokens parameter (new parameter)","params":{"max_completion_tokens":100},"test_param":{"name":"max_completion_tokens","value":100}},{"name":"test_param_user","description":"Test user parameter (user identifier)","params":{"user":"user-123"},"test_param":{"name":"user","value":"user-123"}},{"name":"test_response_format_text","description":"Test response_format as text (default)","params":{"response_format":{"type":"text"}},"test_param":{"name":"response_format.type","value":"text"},"required_fields":["choices[0].message.content"]},{"name":"test_response_format_json_object","description":"Test response_format as json_object","params":{"messages":[{"role":"user","content":"Return JSON: {\"status\": \"ok\"}"}],"response_format":{"type":"json_object"}},"test_param":{"name":"response_format.type","value":"json_object"},"required_fields":["choices[0].message.content"]},{"name":"test_response_format_json_schema","description":"Test response_format as json_schema","params":{"messages":[{"role":"user","content":"Generate a person's info"}],"response_format":{"type":"json_schema","json_schema":{"name":"person","schema":{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"number"}},"required":["name","age"]}}}},"test_param":{"name":"response_format.type","value":"json_schema"},"required_fields":["choices[0].message.content"]},{"name":"test_param_tools","description":"Test tools parameter (function calling)","params":{"messages":[{"role":"user","content":"What's the weather in Beijing?"}],"tools":[{"type":"function","function":{"name":"get_weather","description":"Get current weather","parameters":{"type":"object","properties":{"location":{"type":"string","description":"City name"}},"required":["location"]}}}]},"test_param":{"name":"tools","value":[{"type":"function","function":{"name":"get_weather","description":"Get current weather","parameters":{"type":"object","properties":{"location":{"type":"string","description":"City name"}},"required":["location"]}}}]},"required_fields":["choices[0].message.tool_calls"]},{"name":"test_tool_choice_variants","description":"Test different tool_choice values","parameterize":{"tool_choice":["none","auto","required"]},"params":{"messages":[{"role":"user","content":"What's the weather?"}],"tools":[{"type":"function","function":{"name":"get_weather","description":"Get weather","parameters":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}}],"tool_choice":"$tool_choice"},"required_fields":["choices[0].message.tool_calls"],"test_param":{"name":"tool_choice","value":"$tool_choice"}},{"name":"test_parallel_tool_calls","description":"Test parallel_tool_calls parameter","params":{"messages":[{"role":"user","content":"Call functions"}],"tools":[{"type":"function","function":{"name":"func1","description":"Function 1","parameters":{"type":"object","properties":{}}}}],"parallel_tool_calls":true},"required_fields":["choices[0].message.tool_calls"],"test_param":{"name":"parallel_tool_calls","value":true}},{"name":"test_param_logprobs","description":"Test logprobs parameter","params":{"logprobs":true},"test_param":{"name":"logprobs","value":true},"required_fields":["choices[0].logprobs"]},{"name":"test_param_top_logprobs","description":"Test different top_logprobs values","parameterize":{"top_logprobs":[1,5,10]},"params":{"logprobs":true,"top_logprobs":"$top_logprobs"},"test_param":{"name":"top_logprobs","value":"$top_logprobs"},"required_fields":["choices[0].logprobs.content[0].top_logprobs"]},{"name":"test_streaming_basic","description":"Test basic streaming response","params":{"stream":true},"stream":true,"test_param":{"name":"stream","value":true}},{"name":"test_streaming_with_usage","description":"Test streaming response with usage","params":{"stream":true,"stream_options":{"include_usage":true}},"stream":true,"test_param":{"name":"stream_options.include_usage","value":true}},{"name":"test_param_logit_bias","description":"Test logit_bias parameter","params":{"logit_bias":{"31373":-100}},"test_param":{"name":"logit_bias","value":{"31373":-100}}},{"name":"test_param_service_tier","description":"Test service_tier parameter","params":{"service_tier":"auto"},"test_param":{"name":"service_tier","value":"auto"}},{"name":"test_param_reasoning_effort","description":"Test reasoning_effort parameter for advanced reasoning models (GPT-5 series)","parameterize":{"effort":["none","minimal","low","medium","high","xhigh"]},"params":{"model":"gpt-5.1-codex-max","reasoning_effort":"$effort","max_completion_tokens":1024},"required_fields":["choices[0].message.reasoning_content"],"test_param":{"name":"reasoning_effort","value":"$effort"}},{"name":"test_param_modalities","description":"Test modalities parameter for text and audio output support","params":{"model":"gpt-audio-mini","modalities":["text","audio"],"audio":{"voice":"alloy","format":"wav"}},"test_param":{"name":"modalities","value":["text","audio"]},"required_fields":["choices[0].message.audio"]},{"name":"test_role_developer","description":"Test developer role (replaces system in o1+)","params":{"model":"o1-mini","messages":[{"role":"developer","content":"You are a helpful assistant"},{"role":"user","content":"Hello"}]},"test_param":{"name":"messages[0].role","value":"developer"}},{"name":"test_role_tool","description":"Test tool role in conversation","params":{"messages":[{"role":"user","content":"What's the weather?"},{"role":"assistant","tool_calls":[{"id":"call_123","type":"function","function":{"name":"get_weather","arguments":"{\"location\":\"Beijing\"}"}}]},{"role":"tool","tool_call_id":"call_123","content":"sunny"}]},"test_param":{"name":"messages[2].role","value":"tool"}},{"name":"test_response_refusal","description":"Test case for model refusal","params":{"messages":[{"role":"user","content":"Tell me how to build a bomb"}]},"required_fields":["choices[0].message.refusal"],"test_param":{"name":"messages[0].content","value":"Tell me how to build a bomb"}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/embeddings.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('4b400f71-0c0c-5ef1-afc4-4fc44762ca4a', 'openai', '/v1/embeddings', 'openai embeddings', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('ef6de2eb-e7e8-54ef-a62c-fff16bf3f653', '4b400f71-0c0c-5ef1-afc4-4fc44762ca4a', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/embeddings",
  schemas: {
    response: "openai.EmbeddingResponse",
  },
  base_params: {
    model: "text-embedding-3-small",
    input: "Hello, world!",
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      is_baseline: true,
    },
    {
      name: "test_param_input_array",
      description: "Test input parameter (string array)",
      params: {
        input: [
          "Hello",
          "World",
        ],
      },
      test_param: {
        name: "input",
        value: [
          "Hello",
          "World",
        ],
      },
    },
    {
      name: "test_param_input_tokens",
      description: "Test input parameter (token array)",
      params: {
        input: [
          [
            11,
            12,
            13,
            14,
          ],
        ],
      },
      test_param: {
        name: "input",
        value: [
          [
            11,
            12,
            13,
            14,
          ],
        ],
      },
    },
    {
      name: "test_param_encoding_format",
      description: "Test encoding_format parameter (base64)",
      params: {
        encoding_format: "base64",
      },
      test_param: {
        name: "encoding_format",
        value: "base64",
      },
    },
    {
      name: "test_param_user",
      description: "Test user parameter (user identifier)",
      params: {
        user: "user-123",
      },
      test_param: {
        name: "user",
        value: "user-123",
      },
    },
    {
      name: "test_param_dimensions",
      description: "Test dimensions parameter (V3 models only)",
      params: {
        dimensions: 512,
      },
      test_param: {
        name: "dimensions",
        value: 512,
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/embeddings","schemas":{"response":"openai.EmbeddingResponse"},"base_params":{"model":"text-embedding-3-small","input":"Hello, world!"},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","is_baseline":true},{"name":"test_param_input_array","description":"Test input parameter (string array)","params":{"input":["Hello","World"]},"test_param":{"name":"input","value":["Hello","World"]}},{"name":"test_param_input_tokens","description":"Test input parameter (token array)","params":{"input":[[11,12,13,14]]},"test_param":{"name":"input","value":[[11,12,13,14]]}},{"name":"test_param_encoding_format","description":"Test encoding_format parameter (base64)","params":{"encoding_format":"base64"},"test_param":{"name":"encoding_format","value":"base64"}},{"name":"test_param_user","description":"Test user parameter (user identifier)","params":{"user":"user-123"},"test_param":{"name":"user","value":"user-123"}},{"name":"test_param_dimensions","description":"Test dimensions parameter (V3 models only)","params":{"dimensions":512},"test_param":{"name":"dimensions","value":512}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/images_edits.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('76f70c9a-a9bc-5eb2-bf19-060e0f1bcf0d', 'openai', '/v1/images/edits', 'openai images_edits', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('b5d127b9-b722-52b4-8d62-adc23340c0e1', '76f70c9a-a9bc-5eb2-bf19-060e0f1bcf0d', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/images/edits",
  schemas: {
    response: "openai.ImageResponse",
    stream_chunk: "openai.ImageStreamEvent",
  },
  base_params: {
    model: "gpt-image-1.5",
    prompt: "Replace the background with a blue sky.",
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: gpt-image-1.5 single image + prompt",
      files: {
        image: "assets/images/test_base.png",
      },
      is_baseline: true,
    },
    {
      name: "test_param_response_format_url_dalle2",
      description: "dall-e-2 supports response_format=url",
      params: {
        model: "dall-e-2",
        response_format: "url",
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "response_format",
        value: "url",
      },
    },
    {
      name: "test_param_background_transparent",
      description: "GPT image supports transparent background",
      params: {
        background: "transparent",
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "background",
        value: "transparent",
      },
    },
    {
      name: "test_param_output_format_webp",
      description: "GPT image supports output_format=webp",
      params: {
        output_format: "webp",
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "output_format",
        value: "webp",
      },
    },
    {
      name: "test_param_output_compression",
      description: "GPT image supports output_compression (webp/jpeg)",
      params: {
        output_format: "webp",
        output_compression: 80,
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "output_compression",
        value: 80,
      },
    },
    {
      name: "test_param_size_gpt_landscape",
      description: "GPT image landscape size",
      params: {
        size: "1536x1024",
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "size",
        value: "1536x1024",
      },
    },
    {
      name: "test_param_n_multiple",
      description: "Generate multiple images (n=2)",
      params: {
        n: 2,
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "n",
        value: 2,
      },
    },
    {
      name: "test_param_input_fidelity_high",
      description: "Input fidelity (GPT image model only)",
      params: {
        input_fidelity: "high",
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "input_fidelity",
        value: "high",
      },
    },
    {
      name: "test_param_mask_png",
      description: "Edit with mask",
      params: {},
      files: {
        image: "assets/images/test_base.png",
        mask: "assets/images/test_base.png",
      },
      test_param: {
        name: "mask",
        value: null,
      },
    },
    {
      name: "test_param_user",
      description: "User identifier",
      params: {
        user: "user-123",
      },
      files: {
        image: "assets/images/test_base.png",
      },
      test_param: {
        name: "user",
        value: "user-123",
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/images/edits","schemas":{"response":"openai.ImageResponse","stream_chunk":"openai.ImageStreamEvent"},"base_params":{"model":"gpt-image-1.5","prompt":"Replace the background with a blue sky."},"tests":[{"name":"test_baseline","description":"Baseline test: gpt-image-1.5 single image + prompt","files":{"image":"assets/images/test_base.png"},"is_baseline":true},{"name":"test_param_response_format_url_dalle2","description":"dall-e-2 supports response_format=url","params":{"model":"dall-e-2","response_format":"url"},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"response_format","value":"url"}},{"name":"test_param_background_transparent","description":"GPT image supports transparent background","params":{"background":"transparent"},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"background","value":"transparent"}},{"name":"test_param_output_format_webp","description":"GPT image supports output_format=webp","params":{"output_format":"webp"},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"output_format","value":"webp"}},{"name":"test_param_output_compression","description":"GPT image supports output_compression (webp/jpeg)","params":{"output_format":"webp","output_compression":80},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"output_compression","value":80}},{"name":"test_param_size_gpt_landscape","description":"GPT image landscape size","params":{"size":"1536x1024"},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"size","value":"1536x1024"}},{"name":"test_param_n_multiple","description":"Generate multiple images (n=2)","params":{"n":2},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"n","value":2}},{"name":"test_param_input_fidelity_high","description":"Input fidelity (GPT image model only)","params":{"input_fidelity":"high"},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"input_fidelity","value":"high"}},{"name":"test_param_mask_png","description":"Edit with mask","params":{},"files":{"image":"assets/images/test_base.png","mask":"assets/images/test_base.png"},"test_param":{"name":"mask","value":null}},{"name":"test_param_user","description":"User identifier","params":{"user":"user-123"},"files":{"image":"assets/images/test_base.png"},"test_param":{"name":"user","value":"user-123"}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/images_generations.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('50569fe4-eb26-566a-9710-ac46c8bb6284', 'openai', '/v1/images/generations', 'openai images_generations', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('ab50f976-30d5-5094-b0eb-f4e1d23153f6', '50569fe4-eb26-566a-9710-ac46c8bb6284', 1, $llmspec${
  provider: "openai",
  endpoint: "/v1/images/generations",
  schemas: {
    response: "openai.ImageResponse",
    stream_chunk: "openai.ImageStreamEvent",
  },
  base_params: {
    model: "dall-e-3",
    prompt: "A cute cat",
    n: 1,
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      is_baseline: true,
    },
    {
      name: "test_param_size",
      description: "Test size parameter (dall-e-3 default size)",
      params: {
        size: "1024x1024",
      },
      test_param: {
        name: "size",
        value: "1024x1024",
      },
    },
    {
      name: "test_param_size_dalle2",
      description: "Test size parameter (dall-e-2 size variants)",
      parameterize: {
        size: [
          "512x512",
          "256x256",
        ],
      },
      params: {
        model: "dall-e-2",
        size: "$size",
      },
      test_param: {
        name: "size",
        value: "$size",
      },
    },
    {
      name: "test_param_size_dalle3",
      description: "Test dall-e-3 size variants",
      parameterize: {
        size: [
          "1792x1024",
          "1024x1792",
        ],
      },
      params: {
        size: "$size",
      },
      test_param: {
        name: "size",
        value: "$size",
      },
    },
    {
      name: "test_param_quality_dalle3",
      description: "Test quality parameter (dall-e-3)",
      parameterize: {
        quality: [
          "hd",
          "standard",
        ],
      },
      params: {
        quality: "$quality",
      },
      test_param: {
        name: "quality",
        value: "$quality",
      },
    },
    {
      name: "test_param_response_format",
      description: "Test response_format parameter (dall-e-3/dall-e-2)",
      parameterize: {
        response_format: [
          "url",
          "b64_json",
        ],
      },
      params: {
        response_format: "$response_format",
      },
      test_param: {
        name: "response_format",
        value: "$response_format",
      },
    },
    {
      name: "test_param_style",
      description: "Test style parameter (dall-e-3)",
      parameterize: {
        style: [
          "vivid",
          "natural",
        ],
      },
      params: {
        style: "$style",
      },
      test_param: {
        name: "style",
        value: "$style",
      },
    },
    {
      name: "test_param_n_dalle2",
      description: "Test n parameter (dall-e-2 supports multiple)",
      params: {
        model: "dall-e-2",
        n: 2,
      },
      test_param: {
        name: "n",
        value: 2,
      },
    },
    {
      name: "test_param_user",
      description: "Test user parameter",
      params: {
        user: "user-123",
      },
      test_param: {
        name: "user",
        value: "user-123",
      },
    },
    {
      name: "test_gpt_image_background_transparent",
      description: "Test background parameter (transparent background, GPT image model)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A simple logo with a transparent background",
        background: "transparent",
        output_format: "png",
      },
      test_param: {
        name: "background",
        value: "transparent",
      },
    },
    {
      name: "test_gpt_image_output_formats",
      description: "Test output_format variants (GPT image model)",
      parameterize: {
        output_format: [
          "png",
          "jpeg",
          "webp",
        ],
      },
      params: {
        model: "gpt-image-1.5",
        prompt: "A minimal illustration of a rocket",
        output_format: "$output_format",
      },
      test_param: {
        name: "output_format",
        value: "$output_format",
      },
    },
    {
      name: "test_gpt_image_output_webp_compression",
      description: "Test output_format=webp + output_compression (GPT image model)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A futuristic city skyline",
        output_format: "webp",
        output_compression: 80,
      },
      test_param: {
        name: "output_compression",
        value: 80,
      },
    },
    {
      name: "test_gpt_image_output_jpeg_compression",
      description: "Test output_format=jpeg + output_compression (GPT image model)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A portrait photo realistic style",
        output_format: "jpeg",
        output_compression: 80,
      },
      test_param: {
        name: "output_compression",
        value: 80,
      },
    },
    {
      name: "test_gpt_image_background_variants",
      description: "Test background variants (GPT image model)",
      parameterize: {
        background: [
          "transparent",
          "opaque",
          "auto",
        ],
      },
      params: {
        model: "gpt-image-1.5",
        prompt: "A product icon with specified background",
        background: "$background",
      },
      test_param: {
        name: "background",
        value: "$background",
      },
    },
    {
      name: "test_gpt_image_moderation_low",
      description: "Test moderation=low (GPT image model)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A landscape painting with trees and river",
        moderation: "low",
      },
      test_param: {
        name: "moderation",
        value: "low",
      },
    },
    {
      name: "test_gpt_image_moderation_auto",
      description: "Test moderation=auto (GPT image model)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A sketch of a city skyline",
        moderation: "auto",
      },
      test_param: {
        name: "moderation",
        value: "auto",
      },
    },
    {
      name: "test_gpt_image_quality_high",
      description: "Test quality=high (GPT image model)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A detailed illustration of a spaceship cockpit",
        quality: "high",
      },
      test_param: {
        name: "quality",
        value: "high",
      },
    },
    {
      name: "test_gpt_image_quality_variants",
      description: "Test other quality values (GPT image model)",
      parameterize: {
        quality: [
          "medium",
          "low",
          "auto",
        ],
      },
      params: {
        model: "gpt-image-1.5",
        prompt: "A clean line-art illustration",
        quality: "$quality",
      },
      test_param: {
        name: "quality",
        value: "$quality",
      },
    },
    {
      name: "test_gpt_image_n_multiple",
      description: "Test n parameter (GPT image model, multiple generation)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A set of minimal icons",
        n: 2,
      },
      test_param: {
        name: "n",
        value: 2,
      },
    },
    {
      name: "test_gpt_image_sizes",
      description: "Test size parameter (GPT image model)",
      parameterize: {
        size: [
          "1024x1024",
          "1536x1024",
          "1024x1536",
        ],
      },
      params: {
        model: "gpt-image-1.5",
        prompt: "A landscape or portrait illustration",
        size: "$size",
      },
      test_param: {
        name: "size",
        value: "$size",
      },
    },
    {
      name: "test_gpt_image_partial_streaming",
      description: "Test partial_images + stream (GPT image model streaming)",
      params: {
        model: "gpt-image-1.5",
        prompt: "A painting of a mountain lake",
        partial_images: true,
        stream: true,
      },
      stream: true,
      test_param: {
        name: "stream",
        value: true,
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"openai","endpoint":"/v1/images/generations","schemas":{"response":"openai.ImageResponse","stream_chunk":"openai.ImageStreamEvent"},"base_params":{"model":"dall-e-3","prompt":"A cute cat","n":1},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","is_baseline":true},{"name":"test_param_size","description":"Test size parameter (dall-e-3 default size)","params":{"size":"1024x1024"},"test_param":{"name":"size","value":"1024x1024"}},{"name":"test_param_size_dalle2","description":"Test size parameter (dall-e-2 size variants)","parameterize":{"size":["512x512","256x256"]},"params":{"model":"dall-e-2","size":"$size"},"test_param":{"name":"size","value":"$size"}},{"name":"test_param_size_dalle3","description":"Test dall-e-3 size variants","parameterize":{"size":["1792x1024","1024x1792"]},"params":{"size":"$size"},"test_param":{"name":"size","value":"$size"}},{"name":"test_param_quality_dalle3","description":"Test quality parameter (dall-e-3)","parameterize":{"quality":["hd","standard"]},"params":{"quality":"$quality"},"test_param":{"name":"quality","value":"$quality"}},{"name":"test_param_response_format","description":"Test response_format parameter (dall-e-3/dall-e-2)","parameterize":{"response_format":["url","b64_json"]},"params":{"response_format":"$response_format"},"test_param":{"name":"response_format","value":"$response_format"}},{"name":"test_param_style","description":"Test style parameter (dall-e-3)","parameterize":{"style":["vivid","natural"]},"params":{"style":"$style"},"test_param":{"name":"style","value":"$style"}},{"name":"test_param_n_dalle2","description":"Test n parameter (dall-e-2 supports multiple)","params":{"model":"dall-e-2","n":2},"test_param":{"name":"n","value":2}},{"name":"test_param_user","description":"Test user parameter","params":{"user":"user-123"},"test_param":{"name":"user","value":"user-123"}},{"name":"test_gpt_image_background_transparent","description":"Test background parameter (transparent background, GPT image model)","params":{"model":"gpt-image-1.5","prompt":"A simple logo with a transparent background","background":"transparent","output_format":"png"},"test_param":{"name":"background","value":"transparent"}},{"name":"test_gpt_image_output_formats","description":"Test output_format variants (GPT image model)","parameterize":{"output_format":["png","jpeg","webp"]},"params":{"model":"gpt-image-1.5","prompt":"A minimal illustration of a rocket","output_format":"$output_format"},"test_param":{"name":"output_format","value":"$output_format"}},{"name":"test_gpt_image_output_webp_compression","description":"Test output_format=webp + output_compression (GPT image model)","params":{"model":"gpt-image-1.5","prompt":"A futuristic city skyline","output_format":"webp","output_compression":80},"test_param":{"name":"output_compression","value":80}},{"name":"test_gpt_image_output_jpeg_compression","description":"Test output_format=jpeg + output_compression (GPT image model)","params":{"model":"gpt-image-1.5","prompt":"A portrait photo realistic style","output_format":"jpeg","output_compression":80},"test_param":{"name":"output_compression","value":80}},{"name":"test_gpt_image_background_variants","description":"Test background variants (GPT image model)","parameterize":{"background":["transparent","opaque","auto"]},"params":{"model":"gpt-image-1.5","prompt":"A product icon with specified background","background":"$background"},"test_param":{"name":"background","value":"$background"}},{"name":"test_gpt_image_moderation_low","description":"Test moderation=low (GPT image model)","params":{"model":"gpt-image-1.5","prompt":"A landscape painting with trees and river","moderation":"low"},"test_param":{"name":"moderation","value":"low"}},{"name":"test_gpt_image_moderation_auto","description":"Test moderation=auto (GPT image model)","params":{"model":"gpt-image-1.5","prompt":"A sketch of a city skyline","moderation":"auto"},"test_param":{"name":"moderation","value":"auto"}},{"name":"test_gpt_image_quality_high","description":"Test quality=high (GPT image model)","params":{"model":"gpt-image-1.5","prompt":"A detailed illustration of a spaceship cockpit","quality":"high"},"test_param":{"name":"quality","value":"high"}},{"name":"test_gpt_image_quality_variants","description":"Test other quality values (GPT image model)","parameterize":{"quality":["medium","low","auto"]},"params":{"model":"gpt-image-1.5","prompt":"A clean line-art illustration","quality":"$quality"},"test_param":{"name":"quality","value":"$quality"}},{"name":"test_gpt_image_n_multiple","description":"Test n parameter (GPT image model, multiple generation)","params":{"model":"gpt-image-1.5","prompt":"A set of minimal icons","n":2},"test_param":{"name":"n","value":2}},{"name":"test_gpt_image_sizes","description":"Test size parameter (GPT image model)","parameterize":{"size":["1024x1024","1536x1024","1024x1536"]},"params":{"model":"gpt-image-1.5","prompt":"A landscape or portrait illustration","size":"$size"},"test_param":{"name":"size","value":"$size"}},{"name":"test_gpt_image_partial_streaming","description":"Test partial_images + stream (GPT image model streaming)","params":{"model":"gpt-image-1.5","prompt":"A painting of a mountain lake","partial_images":true,"stream":true},"stream":true,"test_param":{"name":"stream","value":true}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/openai/responses.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('9cc47ae8-5570-50af-a8d5-998868a85f4f', 'openai', '/v1/responses', 'OpenAI Responses', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('f1b001b0-6068-53c2-9b61-a864b37a7ab7', '9cc47ae8-5570-50af-a8d5-998868a85f4f', 1, $llmspec${
  suite_name: "OpenAI Responses",
  provider: "openai",
  endpoint: "/v1/responses",
  schemas: {
    response: "openai.ResponseObject",
    stream_chunk: "openai.ResponsesStreamEvent",
  },
  method: "POST",
  base_params: {
    model: "gpt-4o-mini",
    input: "Say hello",
  },
  stream_rules: {
    // OpenAI Responses streaming ends with "data: [DONE]" (parser maps it to "[DONE]").
    min_observations: 1,
    checks: [
      {
        type: "required_sequence",
        values: [
          "response.created",
          "response.output_item.added",
          "response.content_part.added",
          "response.output_text.delta",
          "response.output_text.done",
          "response.content_part.done",
          "response.output_item.done",
          "response.completed",
          "[DONE]",
        ],
      },
      {
        type: "required_terminal",
        value: "[DONE]",
      },
    ],
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test: only required parameters",
      is_baseline: true,
    },
    {
      name: "test_input_string",
      description: "Test input parameter (string format)",
      params: {
        input: "Hello, how are you?",
      },
      test_param: {
        name: "input",
        value: "Hello, how are you?",
      },
    },
    {
      name: "test_input_array_text",
      description: "Test input parameter (array format, text messages)",
      params: {
        input: [
          {
            type: "message",
            role: "user",
            content: "Say hello",
          },
        ],
      },
      test_param: {
        name: "input",
        value: [
          {
            type: "message",
            role: "user",
            content: "Say hello",
          },
        ],
      },
    },
    {
      name: "test_param_instructions",
      description: "Test instructions parameter",
      params: {
        instructions: "You are a helpful assistant.",
      },
      test_param: {
        name: "instructions",
        value: "You are a helpful assistant.",
      },
    },
    {
      name: "test_param_temperature",
      description: "Test temperature parameter",
      params: {
        temperature: 0.7,
      },
      test_param: {
        name: "temperature",
        value: 0.7,
      },
    },
    {
      name: "test_param_top_p",
      description: "Test top_p parameter",
      params: {
        top_p: 0.9,
      },
      test_param: {
        name: "top_p",
        value: 0.9,
      },
    },
    {
      name: "test_param_max_output_tokens",
      description: "Test max_output_tokens parameter",
      params: {
        max_output_tokens: 100,
      },
      test_param: {
        name: "max_output_tokens",
        value: 100,
      },
    },
    {
      name: "test_param_metadata",
      description: "Test metadata parameter",
      params: {
        metadata: {
          user_id: "123",
          session: "abc",
        },
      },
      test_param: {
        name: "metadata",
        value: {
          user_id: "123",
          session: "abc",
        },
      },
    },
    {
      name: "test_text_format_text",
      description: "Test text parameter (format: text)",
      params: {
        text: {
          format: {
            type: "text",
          },
        },
      },
      test_param: {
        name: "text.format.type",
        value: "text",
      },
    },
    {
      name: "test_text_format_json_object",
      description: "Test text parameter (format: json_object)",
      params: {
        input: "Return JSON: {\"status\": \"ok\"}",
        text: {
          format: {
            type: "json_object",
          },
        },
      },
      test_param: {
        name: "text.format.type",
        value: "json_object",
      },
    },
    {
      name: "test_text_format_json_schema",
      description: "Test text parameter (format: json_schema)",
      params: {
        input: "Generate a person's info",
        text: {
          format: {
            type: "json_schema",
            schema: {
              type: "object",
              properties: {
                name: {
                  type: "string",
                },
                age: {
                  type: "number",
                },
              },
              required: [
                "name",
                "age",
              ],
            },
          },
        },
      },
      test_param: {
        name: "text.format.type",
        value: "json_schema",
      },
    },
    {
      name: "test_tools_function",
      description: "Test tools parameter (custom function)",
      params: {
        input: "What's the weather in Beijing?",
        tools: [
          {
            type: "function",
            "function": {
              name: "get_weather",
              description: "Get current weather",
              parameters: {
                type: "object",
                properties: {
                  location: {
                    type: "string",
                    description: "City name",
                  },
                },
                required: [
                  "location",
                ],
              },
            },
          },
        ],
      },
      test_param: {
        name: "tools",
        value: [
          {
            type: "function",
            "function": {
              name: "get_weather",
              description: "Get current weather",
              parameters: {
                type: "object",
                properties: {
                  location: {
                    type: "string",
                    description: "City name",
                  },
                },
                required: [
                  "location",
                ],
              },
            },
          },
        ],
      },
    },
    {
      name: "test_tools_file_search",
      description: "Test tools parameter (built-in file search tool)",
      params: {
        input: "Search for documentation",
        tools: [
          {
            type: "file_search",
          },
        ],
      },
      test_param: {
        name: "tools",
        value: [
          {
            type: "file_search",
          },
        ],
      },
    },
    {
      name: "test_tools_web_search",
      description: "Test tools parameter (built-in web search tool)",
      params: {
        input: "Search the web for latest news",
        tools: [
          {
            type: "web_search",
          },
        ],
      },
      test_param: {
        name: "tools",
        value: [
          {
            type: "web_search",
          },
        ],
      },
    },
    {
      name: "test_tools_code_interpreter",
      description: "Test tools parameter (built-in code interpreter tool)",
      params: {
        input: "Calculate 15 * 27",
        tools: [
          {
            type: "code_interpreter",
          },
        ],
      },
      test_param: {
        name: "tools",
        value: [
          {
            type: "code_interpreter",
          },
        ],
      },
    },
    {
      name: "test_tool_choice_variants",
      description: "Test different tool_choice values",
      parameterize: {
        tool_choice: [
          "none",
          "auto",
          "required",
        ],
      },
      params: {
        input: "What's the weather?",
        tools: [
          {
            type: "function",
            "function": {
              name: "get_weather",
              description: "Get weather",
              parameters: {
                type: "object",
                properties: {
                  location: {
                    type: "string",
                  },
                },
                required: [
                  "location",
                ],
              },
            },
          },
        ],
        tool_choice: "$tool_choice",
      },
      test_param: {
        name: "tool_choice",
        value: "$tool_choice",
      },
    },
    {
      name: "test_parallel_tool_calls",
      description: "Test parallel_tool_calls parameter",
      params: {
        input: "Call functions",
        tools: [
          {
            type: "function",
            "function": {
              name: "func1",
              description: "Function 1",
              parameters: {
                type: "object",
                properties: {},
              },
            },
          },
        ],
        parallel_tool_calls: true,
      },
      test_param: {
        name: "parallel_tool_calls",
        value: true,
      },
    },
    {
      name: "test_param_store",
      description: "Test store parameter",
      params: {
        store: false,
      },
      test_param: {
        name: "store",
        value: false,
      },
    },
    {
      name: "test_param_service_tier",
      description: "Test service_tier parameter",
      params: {
        service_tier: "auto",
      },
      test_param: {
        name: "service_tier",
        value: "auto",
      },
    },
    {
      name: "test_param_safety_identifier",
      description: "Test safety_identifier parameter",
      params: {
        safety_identifier: "user_hash_123",
      },
      test_param: {
        name: "safety_identifier",
        value: "user_hash_123",
      },
    },
    {
      name: "test_param_max_tool_calls",
      description: "Test max_tool_calls parameter",
      params: {
        input: "Search for information",
        tools: [
          {
            type: "web_search",
          },
        ],
        max_tool_calls: 5,
      },
      test_param: {
        name: "max_tool_calls",
        value: 5,
      },
    },
    {
      name: "test_param_truncation",
      description: "Test truncation parameter",
      params: {
        truncation: "auto",
      },
      test_param: {
        name: "truncation",
        value: "auto",
      },
    },
    {
      name: "test_streaming_basic",
      description: "Test basic streaming response",
      params: {
        stream: true,
      },
      stream: true,
      test_param: {
        name: "stream",
        value: true,
      },
    },
  ],
}
$llmspec$, $llmspec${"suite_name":"OpenAI Responses","provider":"openai","endpoint":"/v1/responses","schemas":{"response":"openai.ResponseObject","stream_chunk":"openai.ResponsesStreamEvent"},"method":"POST","base_params":{"model":"gpt-4o-mini","input":"Say hello"},"stream_rules":{"min_observations":1,"checks":[{"type":"required_sequence","values":["response.created","response.output_item.added","response.content_part.added","response.output_text.delta","response.output_text.done","response.content_part.done","response.output_item.done","response.completed","[DONE]"]},{"type":"required_terminal","value":"[DONE]"}]},"tests":[{"name":"test_baseline","description":"Baseline test: only required parameters","is_baseline":true},{"name":"test_input_string","description":"Test input parameter (string format)","params":{"input":"Hello, how are you?"},"test_param":{"name":"input","value":"Hello, how are you?"}},{"name":"test_input_array_text","description":"Test input parameter (array format, text messages)","params":{"input":[{"type":"message","role":"user","content":"Say hello"}]},"test_param":{"name":"input","value":[{"type":"message","role":"user","content":"Say hello"}]}},{"name":"test_param_instructions","description":"Test instructions parameter","params":{"instructions":"You are a helpful assistant."},"test_param":{"name":"instructions","value":"You are a helpful assistant."}},{"name":"test_param_temperature","description":"Test temperature parameter","params":{"temperature":0.7},"test_param":{"name":"temperature","value":0.7}},{"name":"test_param_top_p","description":"Test top_p parameter","params":{"top_p":0.9},"test_param":{"name":"top_p","value":0.9}},{"name":"test_param_max_output_tokens","description":"Test max_output_tokens parameter","params":{"max_output_tokens":100},"test_param":{"name":"max_output_tokens","value":100}},{"name":"test_param_metadata","description":"Test metadata parameter","params":{"metadata":{"user_id":"123","session":"abc"}},"test_param":{"name":"metadata","value":{"user_id":"123","session":"abc"}}},{"name":"test_text_format_text","description":"Test text parameter (format: text)","params":{"text":{"format":{"type":"text"}}},"test_param":{"name":"text.format.type","value":"text"}},{"name":"test_text_format_json_object","description":"Test text parameter (format: json_object)","params":{"input":"Return JSON: {\"status\": \"ok\"}","text":{"format":{"type":"json_object"}}},"test_param":{"name":"text.format.type","value":"json_object"}},{"name":"test_text_format_json_schema","description":"Test text parameter (format: json_schema)","params":{"input":"Generate a person's info","text":{"format":{"type":"json_schema","schema":{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"number"}},"required":["name","age"]}}}},"test_param":{"name":"text.format.type","value":"json_schema"}},{"name":"test_tools_function","description":"Test tools parameter (custom function)","params":{"input":"What's the weather in Beijing?","tools":[{"type":"function","function":{"name":"get_weather","description":"Get current weather","parameters":{"type":"object","properties":{"location":{"type":"string","description":"City name"}},"required":["location"]}}}]},"test_param":{"name":"tools","value":[{"type":"function","function":{"name":"get_weather","description":"Get current weather","parameters":{"type":"object","properties":{"location":{"type":"string","description":"City name"}},"required":["location"]}}}]}},{"name":"test_tools_file_search","description":"Test tools parameter (built-in file search tool)","params":{"input":"Search for documentation","tools":[{"type":"file_search"}]},"test_param":{"name":"tools","value":[{"type":"file_search"}]}},{"name":"test_tools_web_search","description":"Test tools parameter (built-in web search tool)","params":{"input":"Search the web for latest news","tools":[{"type":"web_search"}]},"test_param":{"name":"tools","value":[{"type":"web_search"}]}},{"name":"test_tools_code_interpreter","description":"Test tools parameter (built-in code interpreter tool)","params":{"input":"Calculate 15 * 27","tools":[{"type":"code_interpreter"}]},"test_param":{"name":"tools","value":[{"type":"code_interpreter"}]}},{"name":"test_tool_choice_variants","description":"Test different tool_choice values","parameterize":{"tool_choice":["none","auto","required"]},"params":{"input":"What's the weather?","tools":[{"type":"function","function":{"name":"get_weather","description":"Get weather","parameters":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}}],"tool_choice":"$tool_choice"},"test_param":{"name":"tool_choice","value":"$tool_choice"}},{"name":"test_parallel_tool_calls","description":"Test parallel_tool_calls parameter","params":{"input":"Call functions","tools":[{"type":"function","function":{"name":"func1","description":"Function 1","parameters":{"type":"object","properties":{}}}}],"parallel_tool_calls":true},"test_param":{"name":"parallel_tool_calls","value":true}},{"name":"test_param_store","description":"Test store parameter","params":{"store":false},"test_param":{"name":"store","value":false}},{"name":"test_param_service_tier","description":"Test service_tier parameter","params":{"service_tier":"auto"},"test_param":{"name":"service_tier","value":"auto"}},{"name":"test_param_safety_identifier","description":"Test safety_identifier parameter","params":{"safety_identifier":"user_hash_123"},"test_param":{"name":"safety_identifier","value":"user_hash_123"}},{"name":"test_param_max_tool_calls","description":"Test max_tool_calls parameter","params":{"input":"Search for information","tools":[{"type":"web_search"}],"max_tool_calls":5},"test_param":{"name":"max_tool_calls","value":5}},{"name":"test_param_truncation","description":"Test truncation parameter","params":{"truncation":"auto"},"test_param":{"name":"truncation","value":"auto"}},{"name":"test_streaming_basic","description":"Test basic streaming response","params":{"stream":true},"stream":true,"test_param":{"name":"stream","value":true}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- suites/xai/chat_completions.json5
insert into suite (id, provider, endpoint, name, status, latest_version) values ('b6b15034-9c31-5bf3-8d9e-515c17f9d17a', 'xai', '/chat/completions', 'xai chat_completions', 'active', 1) on conflict (provider, endpoint) do update set id=excluded.id, name=excluded.name, status=excluded.status, latest_version=greatest(suite.latest_version, excluded.latest_version), updated_at=now();
insert into suite_version (id, suite_id, version, raw_json5, parsed_json, created_by) values ('f69e725e-97cd-5360-add6-c5ffdbb865bc', 'b6b15034-9c31-5bf3-8d9e-515c17f9d17a', 1, $llmspec${
  provider: "xai",
  endpoint: "/chat/completions",
  schemas: {
    response: "xai.ChatCompletionResponse",
  },
  base_params: {
    model: "grok-beta",
    messages: [
      {
        role: "user",
        content: "Hello",
      },
    ],
  },
  tests: [
    {
      name: "test_baseline",
      description: "Baseline test",
      is_baseline: true,
    },
    {
      name: "test_param_temperature",
      description: "Test temperature parameter",
      params: {
        temperature: 0.7,
      },
      test_param: {
        name: "temperature",
        value: 0.7,
      },
    },
    {
      name: "test_param_max_tokens",
      description: "Test max_tokens parameter",
      params: {
        max_tokens: 100,
      },
      test_param: {
        name: "max_tokens",
        value: 100,
      },
    },
  ],
}
$llmspec$, $llmspec${"provider":"xai","endpoint":"/chat/completions","schemas":{"response":"xai.ChatCompletionResponse"},"base_params":{"model":"grok-beta","messages":[{"role":"user","content":"Hello"}]},"tests":[{"name":"test_baseline","description":"Baseline test","is_baseline":true},{"name":"test_param_temperature","description":"Test temperature parameter","params":{"temperature":0.7},"test_param":{"name":"temperature","value":0.7}},{"name":"test_param_max_tokens","description":"Test max_tokens parameter","params":{"max_tokens":100},"test_param":{"name":"max_tokens","value":100}}]}$llmspec$::jsonb, 'seed') on conflict (suite_id, version) do update set raw_json5=excluded.raw_json5, parsed_json=excluded.parsed_json;

-- END SEED SUITES (generated)
