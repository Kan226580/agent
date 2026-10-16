# 企业技术标写作 Harness Agent API文档

版本：1.0.0；设计日期：2026-10-16。  
Base URL：https://<企业域名>/api/v1  
配套文档：[开发文档](./开发文档.md)、[数据库模型](./数据库模型.md)。  
本文件包含104个首期接口及公开Schema、请求/响应示例和错误语义，是待实现契约，不代表服务已运行。示例均为虚构数据，各接口示例独立展示；UUID和重复的hash仅说明格式，不作为种子数据。

## 1. 通用协议

### 1.1 身份与HTTP语义

login/refresh以外的业务请求携带Authorization: Bearer <access-token>。JWT固定issuer/audience/允许算法，15分钟有效；刷新令牌随机生成、只存hash、轮转、7天绝对有效期。首期refresh_token显式放请求体，前端仅在内存保存，不放URL/localStorage；后续Cookie适配必须HttpOnly/Secure/SameSite及CSRF，不能和当前方式混用。每请求校验用户active及auth_version。

服务端推导org、角色、成员和授权。不可见资源ID返回404 RESOURCE_NOT_FOUND；已知可见资源但操作权限不足返回403 PERMISSION_DENIED。管理员只看配置与脱敏运维内容，不获得正文特权。

路径ID均为UUID，日期RFC3339含时区，Decimal用字符串，JSON UTF-8。写入未知字段422，PATCH至少一项，未提供不变，null仅用于可空字段。同步创建201、长任务202、读取/更新200；业务失败使用正确HTTP状态，不一律200。

### 1.2 响应和公共字段

普通响应：
```json
{"code":"OK","message":"success","data":{"id":"00000000-0000-4000-8000-000000000001"},"request_id":"req-example-001"}
```

错误：
```json
{"code":"VERSION_CONFLICT","message":"资源已变化，请刷新后重试。","data":{"current_lock_version":2,"errors":[]},"request_id":"req-example-001"}
```

422的data.errors为[{field:"body.title",reason:"required",message:"缺少标题"}]。X-Request-ID与正文相同，客户端传入只接受≤100安全字符；无效时服务端新建。错误不包含栈、SQL、供应商凭证或源正文。

ErrorDetail用于Job/Run的error：{schema_version:1,code,message,retryable,stage}。AcceptedJob为{job:Job,resource:{type,id}}，type使用数据库表名，Location指向/api/v1/jobs/{id}。创建run的202直接data=Run，Location指向/api/v1/runs/{id}。二进制和SSE不套JSON；文件流开始后失败只能断流，不追加错误JSON。

### 1.3 分页、ETag、幂等和限流

所有分页列表接受limit=1..100（默认20）、cursor不透明签名游标，返回{items,next_cursor}。常规created_at+id排序；章节/片段按position/ordinal+id。游标绑定筛选和权限范围；无total，避免未授权计数和大范围统计。

GET可变资源返回ETag: "v1"，字段lock_version为1。标注If-Match的写请求必须携带；缺失428，过期409。部分成员/范围配置使用父Project的ETag；章节PATCH响应ETag对应工作区chapter，不是不可变version。

标注幂等的请求必须Idempotency-Key，8..128安全字符，作用域org+user+method+实际路径，保留7天。同key同body回放原资源，同key不同body409；并发提交等待超1秒409 IDEMPOTENCY_IN_PROGRESS和Retry-After:1。业务与幂等响应同事务，重放前重新鉴权。登录刷新、GET和内容PUT不用此键。

默认每账号登录失败5次/分钟（并结合IP）；普通API120次/分钟；检索20次/分钟；任务提交10次/分钟；每人最多5条SSE。超限429并返回秒数Retry-After。HTTP任务接收不占长期连接等待整个标书生成。

### 1.4 类型与字段标记

第4节请求字段：!为必填，?为可选，Q为查询参数，header为头字段。数组写成uuid[]；hash为64位小写十六进制；版本号/排序/页码等integer必须为正数（span_start、计数和游标允许0）；decimal为非负十进制字符串；datetime带时区。conditional必填在接口说明中定义。所有响应字段按第2节模型返回，nullable字段可为null；只读字段不可作为任意写入属性。

公共嵌套类型：
- EgressPolicy：schema_version=1、mode=local_only/cloud_allowlist、provider_ids数组；confidential/restricted仅内网。
- Capabilities：schema_version=1、structured_output、tool_call、context_window；embedding另须dimension=1024。
- Locator：schema_version=1、format=pdf/docx/xlsx；PDF必填page_start/page_end（从1起），bbox可选0..1；DOCX段落ID/heading_path或table_id/row_range；XLSX必填sheet/cell_range。
- ContentDocument：schema_version=1、blocks非空。paragraph={block_id,type,text}；heading另有level1..6；list={block_id,type,ordered,items:string[]}；table={block_id,type,headers:string[],rows:string[][]}且列数一致；image_ref={block_id,type,file_id,caption}仅引用受控解析/模板资产。禁止HTML、脚本和远程URL。
- CitationInput：chunk_id、block_id、span_start、span_end（Unicode码点半开区间）、quote_text、usage_kind=fact/reference/requirement/proposal。id/hash/verification服务端计算。
- OutlineNodeInput：id可省（新增节点服务器分配），parent_id、position、title、target_words、requirement_ids、instructions必填，chapter_id仅允许本项目已有章节或null；新节点批量父引用使用临时client_key/parent_client_key，在一次事务内映射到UUID，不与parent_id同时提供。
- TemplateManifest：schema_version、slots、styles、numbering、page_setup、citation_appendix、font_bundle_hash、validation；仅受控样式/占位，不执行脚本。validation必须关联可信流水线验收记录，客户端声明passed不构成证明。
- InputSnapshot为服务端内部协议，客户端只传明确业务ID，不直接设置graph state/checkpoint/thread。

状态名称见数据库模型第2节。run成功不等于正式定稿。waiting_review只能经审核决定继续。资料/正文/历史版本/检查/导出继承完整来源权限，旧幂等响应与缓存不能绕过撤权。

## 2. 公开读取模型

每个字段均为必返，标“或null”时允许null。类型和含义来自同一数据模型，避免独立命名；API不直接暴露完整ORM行。动态组合对象在下面另列说明。

### 2.1 User

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| username | string(maxLength=100) | 小写规范化登录名 |
| display_name | string(maxLength=100) | 姓名 |
| department_id | uuid或null | 所属单部门 |
| status | string(maxLength=16) | active/disabled |
| lock_version | integer | 资源版本，对应ETag |

### 2.2 Department

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| name | string(maxLength=100) | 部门名 |
| parent_id | uuid或null | 上级 |
| status | string(maxLength=16) | active/disabled |
| lock_version | integer | 资源版本，对应ETag |

### 2.3 Role

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| code | string(maxLength=40) | system_admin/knowledge_admin/user |
| permissions | JSON（按字段结构） | 固定权限码数组 |

### 2.4 Project

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| name | string(maxLength=200) | 项目名 |
| industry | string(maxLength=32) | general/construction/it |
| status | string(maxLength=20) | project_status |
| owner_id | uuid | 负责人 |
| deadline | string(date-time)或null | 截止时间 |
| active_requirement_set_id | uuid或null | 确认要求 |
| active_outline_id | uuid或null | 确认大纲 |
| active_policy_id | uuid或null | 当前策略 |
| finalized_snapshot_id | uuid或null | 定稿 |
| lock_version | integer | 资源版本，对应ETag |

### 2.5 Member

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| user_id | uuid | 用户 |
| role | string(maxLength=20) | owner/writer/reviewer/reader |
| status | string(maxLength=16) | active/disabled |
| lock_version | integer | 资源版本，对应ETag |

### 2.6 ModelProfile

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| logical_key | string(maxLength=80) | 配置系列 |
| version_no | integer | 业务版本 |
| provider | string(maxLength=80) | 供应商 |
| model_name | string(maxLength=200) | 模型名 |
| revision | string(maxLength=200) | 权重/服务版本 |
| purpose | string(maxLength=20) | generation/embedding/rerank/ocr |
| is_cloud | boolean | 出网 |
| capabilities | JSON（按字段结构） | 结构化输出/工具/context/dimension |
| enabled | boolean | 启用 |
| lock_version | integer | 资源版本，对应ETag |

### 2.7 ProjectPolicy

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| version_no | integer | 版本 |
| mode | string(maxLength=24) | local_only/allowlisted_cloud |
| allowed_model_profile_ids | uuid[] | 允许配置 |
| default_model_profile_id | uuid | 默认 |
| max_run_tokens | integer | 额度 |

### 2.8 KnowledgeBase

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| name | string(maxLength=200) | 名称 |
| description | string | 描述 |
| active_generation_id | uuid或null | 活动索引代 |
| status | string(maxLength=20) | active/archived |
| lock_version | integer | 资源版本，对应ETag |

### 2.9 Grant

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| kb_id | uuid或null | 资源之一 |
| document_id | uuid或null | 资源之一 |
| principal_user_id | uuid或null | 主体之一 |
| principal_department_id | uuid或null | 主体之一 |
| principal_project_id | uuid或null | 主体之一 |
| permission | string(maxLength=16) | read/manage |
| expires_at | string(date-time)或null | 过期即撤销 |

### 2.10 UploadSession

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| state | string(maxLength=20) | initiated/uploaded/completed/expired/failed |
| expires_at | string(date-time) | 1小时到期 |
| lock_version | integer | 资源版本，对应ETag |
| upload_url | string | 仅API相对地址 |
| max_bytes | integer | 最大文件字节 |

### 2.11 File

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| original_name | string(maxLength=255) | 显示名 |
| media_type | string(maxLength=120) | 检测MIME |
| size_bytes | integer | 大小 |
| sha256 | string(length=64) | 服务端hash |
| state | string(maxLength=20) | staged/ready/quarantined/deleted |

### 2.12 Document

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid或null | 项目资料 |
| kb_id | uuid或null | 企业资料 |
| title | string(maxLength=300) | 标题 |
| kind | string(maxLength=30) | tender/addendum/qualification/case/technical/reference |
| current_version_id | uuid或null | 当前版本 |
| classification | string(maxLength=20) | internal/confidential/restricted |
| inherit_acl | boolean | 继承范围权限 |
| egress_policy | JSON（按字段结构） | EgressPolicy |
| lock_version | integer | 资源版本，对应ETag |

### 2.13 DocumentVersion

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| document_id | uuid | 逻辑文档 |
| file_id | uuid | 原件 |
| version_no | integer | 递增版本 |
| status | string(maxLength=20) | document_status |
| content_hash | string(length=64)或null | 提取内容摘要 |
| page_count | integer或null | 页数 |
| valid_until | string(date-time)或null | 失效 |
| extraction_report | JSON（按字段结构） | 低置信度、修正映射、复核人及时间 |
| lock_version | integer | 资源版本，对应ETag |

### 2.14 Chunk

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| document_version_id | uuid | 版本 |
| text | string | ≤32768 UTF-8字节 |
| locator | JSON（按字段结构） | Locator |
| content_hash | string(length=64) | 摘要 |

### 2.15 RequirementSet

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| version_no | integer | 业务版本 |
| supersedes_id | uuid或null | 替代版本 |
| status | string(maxLength=20) | draft/analyzing/ready/confirmed/superseded/failed |
| content_hash | string(length=64)或null | 候选/确认摘要 |
| diff_summary | JSON（按字段结构） | 补遗增删改与影响 |
| lock_version | integer | 资源版本，对应ETag |

### 2.16 Requirement

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| code | string(maxLength=80) | 编号 |
| text | string | 原文/确认表述 |
| category | string(maxLength=30) | functional/technical/delivery/format/qualification/other |
| scope | string(maxLength=20) | technical/out_of_scope/needs_human |
| mandatory | boolean | 强制 |
| source_chunk_id | uuid | 出处 |
| locator | JSON（按字段结构） | 精确定位 |
| clarification | string或null | 解释与歧义 |
| lock_version | integer | 资源版本，对应ETag |

### 2.17 ScoringItem

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| requirement_id | uuid | 条款 |
| title | string(maxLength=300) | 名称 |
| max_score | decimal字符串或null | 未知为空 |
| criteria | JSON（按字段结构） | 分档条件 |
| source_chunk_id | uuid | 出处 |
| lock_version | integer | 资源版本，对应ETag |

### 2.18 Template

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| code | string(maxLength=80) | 系列码 |
| name | string(maxLength=200) | 名称 |
| industry | string(maxLength=32) | general/construction/it |
| active_version_id | uuid或null | 发布版本 |
| lock_version | integer | 资源版本，对应ETag |

### 2.19 TemplateVersion

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| template_id | uuid | 系列 |
| version_no | integer | 业务版本 |
| content_hash | string(length=64) | 模板和manifest摘要 |

### 2.20 OutlineNode

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| parent_id | uuid或null | 同大纲父节点 |
| chapter_id | uuid或null | 确认时稳定章节 |
| position | integer | 同级顺序 |
| title | string(maxLength=300) | 标题 |
| target_words | integer | 100..20000中文字符 |
| requirement_ids | uuid[] | 要求关联 |
| instructions | string | 目标 |

### 2.21 Outline

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| requirement_set_id | uuid | 确认要求 |
| template_version_id | uuid | 模板 |
| version_no | integer | 业务版本 |
| status | string(maxLength=20) | draft/ready/confirmed/superseded |
| content_hash | string(length=64)或null | 摘要 |
| lock_version | integer | 资源版本，对应ETag |
| nodes | OutlineNode[] | 节点树 |

### 2.22 Chapter

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| title | string(maxLength=300) | 当前标题 |
| position | integer | 展开顺序 |
| status | string(maxLength=20) | chapter_status |
| current_version_id | uuid或null | 当前正文 |
| lock_version | integer | 资源版本，对应ETag |

### 2.23 ChapterVersion

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| chapter_id | uuid | 章节 |
| version_no | integer | 业务版本 |
| submitted_by | uuid | 业务提交人 |
| content | JSON（按字段结构） | ContentDocument |
| content_hash | string(length=64) | 正文及来源摘要 |
| source_version_ids | uuid[] | 完整来源闭包 |
| citations | Citation[] | 句段引用 |

### 2.24 Citation

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| chunk_id | uuid | 证据 |
| block_id | string(maxLength=80) | 正文块 |
| span_start | integer | Unicode码点起点 |
| span_end | integer | 半开区间终点 |
| quote_text | string | 原文摘录 |
| usage_kind | string(maxLength=20) | fact/reference/requirement/proposal |
| verification | string(maxLength=20) | unverified/supported/unsupported |

### 2.25 Review

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| run_id | uuid或null | 待恢复运行 |
| chapter_version_id | uuid | 目标版本 |
| submitted_by | uuid | 提交人 |
| assigned_to | uuid或null | 指定审核人 |
| status | string(maxLength=16) | review_status |
| lock_version | integer | 资源版本，对应ETag |

### 2.26 Run

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| status | string(maxLength=24) | run_status |
| wait_reason | string(maxLength=80)或null | revision_required/evidence_missing/input_changed/policy_changed/budget_exceeded |
| current_chapter_id | uuid或null | 当前章 |
| workflow_version | string(maxLength=80) | 固定图版本 |
| budget_tokens | integer | 额度 |
| spent_tokens | integer | 已确认消耗 |
| reserved_tokens | integer | 在途/未知预留 |
| lock_version | integer | 资源版本，对应ETag |
| error | JSON（按字段结构）或null | ErrorDetail |
| input_snapshot_hash | hash | 冻结输入摘要 |
| last_event_seq | integer | 最后提交事件序号 |
| events_retained_from | integer | 当前保留事件最小序号，无事件时为高水位+1 |

### 2.27 Job

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| kind | string(maxLength=30) | ingest/index_build/analyze/outline/check/export |
| status | string(maxLength=24) | job_status |
| target_id | uuid | 多态目标 |
| progress | integer | 0..100 |
| attempt | integer | 最多5次 |
| lock_version | integer | 资源版本，对应ETag |
| error | JSON（按字段结构）或null | ErrorDetail |

### 2.28 Check

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| chapter_version_id | uuid或null | 空为全文 |
| status | string(maxLength=20) | queued/running/completed/failed/stale |
| snapshot_hash | string(length=64) | 输入快照 |
| summary | JSON（按字段结构） | 计数和覆盖率 |
| lock_version | integer | 资源版本，对应ETag |

### 2.29 Finding

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| check_id | uuid | 检查 |
| severity | string(maxLength=16) | blocker/warning/info |
| code | string(maxLength=80) | 稳定规则码 |
| message | string | 说明 |
| resolution | object或null | action/note/replacement_check_id |

### 2.30 ResponseMapping

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| requirement_id | uuid | 条款 |
| chapter_version_id | uuid或null | 正文 |
| status | string(maxLength=20) | covered/partial/missing/not_applicable |
| response_summary | string | 响应说明 |
| citation_ids | uuid[] | 证据 |
| reason | string或null | 缺失或不适用理由 |
| lock_version | integer | 资源版本，对应ETag |

### 2.31 FinalizedSnapshot

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| snapshot_hash | string(length=64) | 内容/来源/批准/模板摘要 |
| revoked_at | string(date-time)或null | 撤销 |
| chapter_version_ids | uuid[] | 定稿顺序 |

### 2.32 Export

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| project_id | uuid | 项目 |
| mode | string(maxLength=16) | draft/final |
| status | string(maxLength=20) | export_status |
| snapshot_id | uuid或null | 正式定稿 |
| lock_version | integer | 资源版本，对应ETag |
| files | object[] | file_id/format/download_url，ready才提供 |

### 2.33 Audit

| 字段 | 类型 | 含义 |
|---|---|---|
| id | uuid | 资源ID |
| action | string(maxLength=100) | 稳定动作 |
| resource_type | string(maxLength=80) | 对象类型 |
| resource_id | uuid或null | 对象ID |
| project_id | uuid或null | 范围 |
| result | string(maxLength=20) | allowed/denied/succeeded/failed |
| request_id | string(maxLength=100)或null | HTTP关联 |

### 2.34 SearchResult

| 字段 | 类型 | 含义 |
|---|---|---|
| hits | object[] | chunk_id/document_version_id/text/locator/rank/usage_kind |
| generation_ids | uuid[] | 实际索引代 |
| warnings | string[] | 降级或缺失提示 |

### 2.35 ChapterEdit

| 字段 | 类型 | 含义 |
|---|---|---|
| chapter | Chapter | 更新后工作区 |
| version | ChapterVersion | 新增正文 |

组合响应：Page<T>={items:T[],next_cursor:string|null}；AcceptedJob={job:Job,resource:{type:string,id:uuid}}。未命名的简单响应对象在对应接口中逐字段说明并给出完整示例。

## 3. 接口索引

| 编号 | 方法 | 路径（省略/api/v1） | 权限 | 成功 |
|---|---|---|---|---|
| 1 | POST | /auth/login | 匿名，账号/IP限速 | 200 |
| 2 | POST | /auth/refresh | 有效刷新令牌 | 200 |
| 3 | POST | /auth/logout | 已登录 | 200 |
| 4 | GET | /users/me | 已登录 | 200 |
| 5 | GET | /users | system_admin | 200 |
| 6 | POST | /users | system_admin | 201 |
| 7 | PATCH | /users/{user_id} | system_admin | 200 |
| 8 | PUT | /users/{user_id}/roles | system_admin | 200 |
| 9 | GET | /roles | system_admin | 200 |
| 10 | GET | /departments | 已登录 | 200 |
| 11 | POST | /departments | system_admin | 201 |
| 12 | PATCH | /departments/{department_id} | system_admin | 200 |
| 13 | GET | /model-profiles | system_admin；owner只看可绑定项 | 200 |
| 14 | POST | /model-profiles | system_admin | 201 |
| 15 | PATCH | /model-profiles/{profile_id} | system_admin | 200 |
| 16 | POST | /projects | 已登录且project.create | 201 |
| 17 | GET | /projects | 已登录 | 200 |
| 18 | GET | /projects/{project_id} | 项目成员 | 200 |
| 19 | PATCH | /projects/{project_id} | owner | 200 |
| 20 | POST | /projects/{project_id}/archive | owner | 200 |
| 21 | GET | /projects/{project_id}/members | 项目成员 | 200 |
| 22 | PUT | /projects/{project_id}/members/{user_id} | owner | 200 |
| 23 | POST | /projects/{project_id}/transfer-owner | 当前owner | 200 |
| 24 | GET | /projects/{project_id}/model-policies | owner/writer/reviewer | 200 |
| 25 | POST | /projects/{project_id}/model-policies | owner | 201 |
| 26 | PUT | /projects/{project_id}/knowledge-bases | owner | 200 |
| 27 | POST | /knowledge-bases | knowledge_admin | 201 |
| 28 | GET | /knowledge-bases | 已登录且库read/manage | 200 |
| 29 | GET | /knowledge-bases/{kb_id} | 库read/manage | 200 |
| 30 | PATCH | /knowledge-bases/{kb_id} | 库manage | 200 |
| 31 | POST | /knowledge-bases/{kb_id}/index-generations | 库manage | 202 |
| 32 | GET | /resource-grants | 指定资源manage | 200 |
| 33 | POST | /resource-grants | 资源manage且有可授予权限 | 201 |
| 34 | DELETE | /resource-grants/{grant_id} | 资源manage | 200 |
| 35 | POST | /uploads | 项目owner/writer或库manage；模板需admin | 201 |
| 36 | PUT | /uploads/{upload_id}/content | 创建者且目标仍可写 | 200 |
| 37 | GET | /uploads/{upload_id} | 创建者 | 200 |
| 38 | POST | /uploads/{upload_id}/complete | 创建者且资源可写 | 202 |
| 39 | GET | /files/{file_id} | 对应资料/产物可读 | 200 |
| 40 | GET | /files/{file_id}/content | 资源及全部来源可读 | 200 |
| 41 | GET | /documents | 目标范围read | 200 |
| 42 | GET | /documents/{document_id} | 文档read | 200 |
| 43 | PATCH | /documents/{document_id} | 项目owner或库manage | 200 |
| 44 | DELETE | /documents/{document_id} | 项目owner或库manage | 200 |
| 45 | GET | /documents/{document_id}/versions | 文档read | 200 |
| 46 | GET | /document-versions/{version_id} | 文档read | 200 |
| 47 | GET | /document-versions/{version_id}/chunks | 文档read | 200 |
| 48 | POST | /document-versions/{version_id}/corrections | owner/writer或库manage | 202 |
| 49 | POST | /projects/{project_id}/knowledge-search | owner/writer/reviewer且资料read | 200 |
| 50 | GET | /templates | 已登录 | 200 |
| 51 | POST | /templates | system_admin | 201 |
| 52 | POST | /templates/{template_id}/versions | system_admin | 201 |
| 53 | POST | /projects/{project_id}/requirement-sets | owner/writer | 202 |
| 54 | GET | /projects/{project_id}/requirement-sets | 项目成员且来源read | 200 |
| 55 | GET | /requirement-sets/{set_id} | 项目成员且来源read | 200 |
| 56 | GET | /requirement-sets/{set_id}/requirements | 项目成员且来源read | 200 |
| 57 | POST | /requirement-sets/{set_id}/requirements | owner/writer | 201 |
| 58 | PATCH | /requirements/{requirement_id} | owner/writer | 200 |
| 59 | GET | /requirement-sets/{set_id}/scoring-items | 项目成员且来源read | 200 |
| 60 | POST | /requirement-sets/{set_id}/scoring-items | owner/writer | 201 |
| 61 | PATCH | /scoring-items/{scoring_id} | owner/writer | 200 |
| 62 | POST | /requirement-sets/{set_id}/confirm | owner | 200 |
| 63 | POST | /projects/{project_id}/outlines | owner/writer | 202 |
| 64 | GET | /projects/{project_id}/outlines | 项目成员且来源read | 200 |
| 65 | GET | /outlines/{outline_id} | 项目成员且来源read | 200 |
| 66 | PATCH | /outlines/{outline_id} | owner/writer | 200 |
| 67 | POST | /outlines/{outline_id}/confirm | owner | 200 |
| 68 | GET | /projects/{project_id}/chapters | 项目成员 | 200 |
| 69 | GET | /chapters/{chapter_id} | 项目成员 | 200 |
| 70 | GET | /chapters/{chapter_id}/versions | 项目成员及全部来源read | 200 |
| 71 | GET | /chapter-versions/{version_id} | 项目成员及全部来源read | 200 |
| 72 | PATCH | /chapters/{chapter_id} | owner/writer | 200 |
| 73 | POST | /chapters/{chapter_id}/reviews | owner/writer | 201 |
| 74 | GET | /projects/{project_id}/reviews | owner/writer/reviewer | 200 |
| 75 | GET | /reviews/{review_id} | 项目成员 | 200 |
| 76 | POST | /reviews/{review_id}/decisions | reviewer且非submitted_by | 200 |
| 77 | GET | /projects/{project_id}/response-matrix | 项目成员及正文来源read | 200 |
| 78 | PUT | /requirements/{requirement_id}/response-mappings | owner/writer | 200 |
| 79 | DELETE | /requirements/{requirement_id} | owner/writer | 200 |
| 80 | DELETE | /scoring-items/{scoring_id} | owner/writer | 200 |
| 81 | POST | /projects/{project_id}/runs | owner/writer | 202 |
| 82 | GET | /projects/{project_id}/runs | 项目成员 | 200 |
| 83 | GET | /runs/{run_id} | 项目成员 | 200 |
| 84 | POST | /runs/{run_id}/resume | 发起人或owner；增预算只owner | 202 |
| 85 | POST | /runs/{run_id}/retry | 发起人或owner | 202 |
| 86 | POST | /runs/{run_id}/cancel | 发起人或owner | 202 |
| 87 | GET | /runs/{run_id}/events | 项目成员，连接持续授权 | 200 |
| 88 | GET | /runs/{run_id}/usage | owner或发起人 | 200 |
| 89 | GET | /jobs | 项目或库可读 | 200 |
| 90 | GET | /jobs/{job_id} | 目标范围可读 | 200 |
| 91 | POST | /jobs/{job_id}/retry | 发起人或owner/库manage | 202 |
| 92 | POST | /jobs/{job_id}/cancel | 发起人或owner/库manage | 202 |
| 93 | POST | /projects/{project_id}/checks | owner/writer/reviewer | 202 |
| 94 | GET | /projects/{project_id}/checks | 项目成员及来源read | 200 |
| 95 | GET | /checks/{check_id} | 项目成员及来源read | 200 |
| 96 | GET | /checks/{check_id}/findings | 项目成员及来源read | 200 |
| 97 | POST | /findings/{finding_id}/resolutions | reviewer | 200 |
| 98 | GET | /projects/{project_id}/content-snapshot | owner/writer/reviewer及全部来源read | 200 |
| 99 | POST | /projects/{project_id}/finalize | owner | 201 |
| 100 | POST | /projects/{project_id}/reopen | owner | 200 |
| 101 | POST | /projects/{project_id}/exports | draft:owner/writer；final:owner | 202 |
| 102 | GET | /projects/{project_id}/exports | 项目成员及来源read | 200 |
| 103 | GET | /exports/{export_id} | 项目成员及来源read | 200 |
| 104 | GET | /audit-logs | system_admin看脱敏系统记录；owner看本项目 | 200 |

## 4. 接口详细契约

### 4.1 POST /auth/login

权限：匿名，账号/IP限速。

| 参数 | 类型、必填及约束 |
|---|---|
| username | string!1..100 |
| password | string!1..128 |

失败统一AUTH_INVALID，不泄露账号是否存在。

请求示例：

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "writer01",
  "password": "文档示例口令-不得用于生产"
}
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：access_token（string）、refresh_token（string）、token_type（string）、expires_in（number）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "access_token": "<JWT>",
    "refresh_token": "<随机刷新令牌>",
    "token_type": "Bearer",
    "expires_in": 900
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；特有 AUTH_INVALID。

### 4.2 POST /auth/refresh

权限：有效刷新令牌。

| 参数 | 类型、必填及约束 |
|---|---|
| refresh_token | string! |

轮转；旧令牌重用撤销整族，7天绝对到期。

请求示例：

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "<当前刷新令牌>"
}
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：access_token（string）、refresh_token（string）、token_type（string）、expires_in（number）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "access_token": "<新JWT>",
    "refresh_token": "<新刷新令牌>",
    "token_type": "Bearer",
    "expires_in": 900
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.3 POST /auth/logout

权限：已登录。

| 参数 | 类型、必填及约束 |
|---|---|
| refresh_token | string! |

已撤销也成功，不记录令牌明文。

请求示例：

```http
POST /api/v1/auth/logout
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "refresh_token": "<刷新令牌>"
}
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：revoked（boolean）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "revoked": true
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.4 GET /users/me

权限：已登录。

参数：仅路径参数及通用头，无请求体。

读取自己。

请求示例：

```http
GET /api/v1/users/me
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 User。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000003",
    "username": "writer01",
    "display_name": "编写人甲",
    "department_id": null,
    "status": "active",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.5 GET /users

权限：system_admin。

| 参数 | 类型、必填及约束 |
|---|---|
| Q status | active/disabled? |
| Q department_id | uuid? |

仅管理账号元数据。

请求示例：

```http
GET /api/v1/users?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:User。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000003",
        "username": "writer01",
        "display_name": "编写人甲",
        "department_id": null,
        "status": "active",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.6 POST /users

权限：system_admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| username | string!1..100 |
| display_name | string!1..100 |
| password | string!12..128 |
| department_id | uuid? |

不自动授予项目/资料权限。

请求示例：

```http
POST /api/v1/users
Authorization: Bearer <access-token>
Idempotency-Key: example-users-create-001
Content-Type: application/json

{
  "username": "writer01",
  "display_name": "编写人甲",
  "password": "文档示例口令-2026",
  "department_id": "00000000-0000-4000-8000-000000000002"
}
```

成功响应：HTTP 201，data模型 User。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000003",
    "username": "writer01",
    "display_name": "编写人甲",
    "department_id": null,
    "status": "active",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.7 PATCH /users/{user_id}

权限：system_admin。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| display_name | string?1..100 |
| department_id | uuid|null? |
| status | active/disabled? |

停用撤销会话并暂停其执行任务。

请求示例：

```http
PATCH /api/v1/users/00000000-0000-4000-8000-000000000003
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "status": "disabled"
}
```

成功响应：HTTP 200，data模型 User。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000003",
    "username": "writer01",
    "display_name": "编写人甲",
    "department_id": null,
    "status": "disabled",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.8 PUT /users/{user_id}/roles

权限：system_admin。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| role_ids | uuid[]! |

替换全量角色；使用User ETag，不能移除最后一名active系统管理员。

请求示例：

```http
PUT /api/v1/users/00000000-0000-4000-8000-000000000003/roles
Authorization: Bearer <access-token>
Idempotency-Key: example-users-roles-001
If-Match: "v1"
Content-Type: application/json

{
  "role_ids": [
    "00000000-0000-4000-8000-000000000004"
  ]
}
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：role_ids（array）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "role_ids": [
      "00000000-0000-4000-8000-000000000004"
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.9 GET /roles

权限：system_admin。

参数：仅路径参数及通用头、分页参数，无请求体。

固定角色和权限码，不开放任意权限。

请求示例：

```http
GET /api/v1/roles?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Role。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000004",
        "code": "user",
        "permissions": [
          "project.create"
        ]
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.10 GET /departments

权限：已登录。

参数：仅路径参数及通用头、分页参数，无请求体。

组织目录不包含成员正文资料。

请求示例：

```http
GET /api/v1/departments?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Department。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000002",
        "name": "投标中心",
        "parent_id": null,
        "status": "active",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.11 POST /departments

权限：system_admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| name | string!1..100 |
| parent_id | uuid|null? |

同父名称唯一，父链不成环。

请求示例：

```http
POST /api/v1/departments
Authorization: Bearer <access-token>
Idempotency-Key: example-departments-create-001
Content-Type: application/json

{
  "name": "投标中心",
  "parent_id": null
}
```

成功响应：HTTP 201，data模型 Department。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000002",
    "name": "投标中心",
    "parent_id": null,
    "status": "active",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.12 PATCH /departments/{department_id}

权限：system_admin。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| name | string?1..100 |
| parent_id | uuid|null? |
| status | active/disabled? |

变更触发权限版本更新。

请求示例：

```http
PATCH /api/v1/departments/00000000-0000-4000-8000-000000000002
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "name": "技术投标中心"
}
```

成功响应：HTTP 200，data模型 Department。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000002",
    "name": "技术投标中心",
    "parent_id": null,
    "status": "active",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.13 GET /model-profiles

权限：system_admin；owner只看可绑定项。

参数：仅路径参数及通用头、分页参数，无请求体。

不返回endpoint_ref/secret_ref。

请求示例：

```http
GET /api/v1/model-profiles?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:ModelProfile。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000009",
        "logical_key": "internal-writer",
        "version_no": 1,
        "provider": "enterprise-local",
        "model_name": "approved-model",
        "revision": "pinned-revision",
        "purpose": "generation",
        "is_cloud": false,
        "capabilities": {
          "schema_version": 1,
          "structured_output": true,
          "tool_call": true,
          "context_window": 32768
        },
        "enabled": true,
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.14 POST /model-profiles

权限：system_admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| logical_key | string!<=80 |
| provider | string! |
| model_name | string! |
| revision | string! |
| purpose | generation/embedding/rerank/ocr! |
| is_cloud | boolean! |
| endpoint_ref | string! |
| secret_ref | string|null? |
| capabilities | Capabilities! |

模型配置新增版本；端点必须管理员预登记，拒绝任意URL。

请求示例：

```http
POST /api/v1/model-profiles
Authorization: Bearer <access-token>
Idempotency-Key: example-models-create-001
Content-Type: application/json

{
  "logical_key": "internal-writer",
  "provider": "enterprise-local",
  "model_name": "approved-model",
  "revision": "pinned-revision",
  "purpose": "generation",
  "is_cloud": false,
  "endpoint_ref": "approved-local-endpoint",
  "capabilities": {
    "schema_version": 1,
    "structured_output": true,
    "tool_call": true,
    "context_window": 32768
  }
}
```

成功响应：HTTP 201，data模型 ModelProfile。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000009",
    "logical_key": "internal-writer",
    "version_no": 1,
    "provider": "enterprise-local",
    "model_name": "approved-model",
    "revision": "pinned-revision",
    "purpose": "generation",
    "is_cloud": false,
    "capabilities": {
      "schema_version": 1,
      "structured_output": true,
      "tool_call": true,
      "context_window": 32768
    },
    "enabled": true,
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.15 PATCH /model-profiles/{profile_id}

权限：system_admin。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| enabled | boolean! |

仅启停可原地改；影响run转waiting_input，不自动换云模型。

请求示例：

```http
PATCH /api/v1/model-profiles/00000000-0000-4000-8000-000000000009
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "enabled": false
}
```

成功响应：HTTP 200，data模型 ModelProfile。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000009",
    "logical_key": "internal-writer",
    "version_no": 1,
    "provider": "enterprise-local",
    "model_name": "approved-model",
    "revision": "pinned-revision",
    "purpose": "generation",
    "is_cloud": false,
    "capabilities": {
      "schema_version": 1,
      "structured_output": true,
      "tool_call": true,
      "context_window": 32768
    },
    "enabled": false,
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.16 POST /projects

权限：已登录且project.create。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| name | string!1..200 |
| industry | general/construction/it! |
| deadline | datetime|null? |

创建者owner，初态draft，配置有效policy后active。

请求示例：

```http
POST /api/v1/projects
Authorization: Bearer <access-token>
Idempotency-Key: example-projects-create-001
Content-Type: application/json

{
  "name": "示例技术服务项目",
  "industry": "it",
  "deadline": "2026-11-15T09:00:00+08:00"
}
```

成功响应：HTTP 201，data模型 Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000007",
    "name": "示例技术服务项目",
    "industry": "it",
    "status": "draft",
    "owner_id": "00000000-0000-4000-8000-000000000003",
    "deadline": "2026-11-15T09:00:00+08:00",
    "active_requirement_set_id": null,
    "active_outline_id": null,
    "active_policy_id": null,
    "finalized_snapshot_id": null,
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.17 GET /projects

权限：已登录。

| 参数 | 类型、必填及约束 |
|---|---|
| Q status | project_status? |
| Q industry | general/construction/it? |

仅本人可见项目，无未授权total。

请求示例：

```http
GET /api/v1/projects?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000007",
        "name": "示例技术服务项目",
        "industry": "it",
        "status": "active",
        "owner_id": "00000000-0000-4000-8000-000000000003",
        "deadline": "2026-11-15T09:00:00+08:00",
        "active_requirement_set_id": "00000000-0000-4000-8000-000000000021",
        "active_outline_id": "00000000-0000-4000-8000-000000000027",
        "active_policy_id": "00000000-0000-4000-8000-000000000010",
        "finalized_snapshot_id": null,
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.18 GET /projects/{project_id}

权限：项目成员。

参数：仅路径参数及通用头，无请求体。

返回ETag，正文仍检查来源。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000007",
    "name": "示例技术服务项目",
    "industry": "it",
    "status": "active",
    "owner_id": "00000000-0000-4000-8000-000000000003",
    "deadline": "2026-11-15T09:00:00+08:00",
    "active_requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "active_outline_id": "00000000-0000-4000-8000-000000000027",
    "active_policy_id": "00000000-0000-4000-8000-000000000010",
    "finalized_snapshot_id": null,
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.19 PATCH /projects/{project_id}

权限：owner。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| name | string?1..200 |
| deadline | datetime|null? |

不能直接改owner/status/active指针。

请求示例：

```http
PATCH /api/v1/projects/00000000-0000-4000-8000-000000000007
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "name": "示例技术服务项目（修订）"
}
```

成功响应：HTTP 200，data模型 Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000007",
    "name": "示例技术服务项目（修订）",
    "industry": "it",
    "status": "active",
    "owner_id": "00000000-0000-4000-8000-000000000003",
    "deadline": "2026-11-15T09:00:00+08:00",
    "active_requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "active_outline_id": "00000000-0000-4000-8000-000000000027",
    "active_policy_id": "00000000-0000-4000-8000-000000000010",
    "finalized_snapshot_id": null,
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.20 POST /projects/{project_id}/archive

权限：owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | string!1..1000 |

有活动run/job返回ACTIVE_TASK_EXISTS；归档后只读。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/archive
Authorization: Bearer <access-token>
Idempotency-Key: example-projects-archive-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "项目已结束。"
}
```

成功响应：HTTP 200，data模型 Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000007",
    "name": "示例技术服务项目",
    "industry": "it",
    "status": "archived",
    "owner_id": "00000000-0000-4000-8000-000000000003",
    "deadline": "2026-11-15T09:00:00+08:00",
    "active_requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "active_outline_id": "00000000-0000-4000-8000-000000000027",
    "active_policy_id": "00000000-0000-4000-8000-000000000010",
    "finalized_snapshot_id": null,
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；特有 ACTIVE_TASK_EXISTS。

### 4.21 GET /projects/{project_id}/members

权限：项目成员。

参数：仅路径参数及通用头、分页参数，无请求体。

只列本项目。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/members?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Member。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000008",
        "user_id": "00000000-0000-4000-8000-000000000003",
        "role": "writer",
        "status": "active",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.22 PUT /projects/{project_id}/members/{user_id}

权限：owner。必需Idempotency-Key。必需If-Match（父Project）。

| 参数 | 类型、必填及约束 |
|---|---|
| role | writer/reviewer/reader! |
| status | active/disabled! |

新增或全量替换；校验父Project ETag，owner转移走专用接口。

请求示例：

```http
PUT /api/v1/projects/00000000-0000-4000-8000-000000000007/members/00000000-0000-4000-8000-000000000003
Authorization: Bearer <access-token>
Idempotency-Key: example-members-put-001
If-Match: "v1"
Content-Type: application/json

{
  "role": "writer",
  "status": "active"
}
```

成功响应：HTTP 200，data模型 Member。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000008",
    "user_id": "00000000-0000-4000-8000-000000000003",
    "role": "writer",
    "status": "active",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.23 POST /projects/{project_id}/transfer-owner

权限：当前owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| new_owner_id | uuid! |

新owner必须现有active成员；旧owner转writer，不自动扩大资料权限。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/transfer-owner
Authorization: Bearer <access-token>
Idempotency-Key: example-projects-transfer-001
If-Match: "v1"
Content-Type: application/json

{
  "new_owner_id": "00000000-0000-4000-8000-000000000900"
}
```

成功响应：HTTP 200，data模型 Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000007",
    "name": "示例技术服务项目",
    "industry": "it",
    "status": "active",
    "owner_id": "00000000-0000-4000-8000-000000000900",
    "deadline": "2026-11-15T09:00:00+08:00",
    "active_requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "active_outline_id": "00000000-0000-4000-8000-000000000027",
    "active_policy_id": "00000000-0000-4000-8000-000000000010",
    "finalized_snapshot_id": null,
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.24 GET /projects/{project_id}/model-policies

权限：owner/writer/reviewer。

参数：仅路径参数及通用头、分页参数，无请求体。

不可变策略历史。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/model-policies?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:ProjectPolicy。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000010",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "version_no": 1,
        "mode": "local_only",
        "allowed_model_profile_ids": [
          "00000000-0000-4000-8000-000000000009"
        ],
        "default_model_profile_id": "00000000-0000-4000-8000-000000000009",
        "max_run_tokens": 300000
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.25 POST /projects/{project_id}/model-policies

权限：owner。必需Idempotency-Key。必需If-Match（父Project）。

| 参数 | 类型、必填及约束 |
|---|---|
| mode | local_only/allowlisted_cloud! |
| allowed_model_profile_ids | uuid[]!min1 |
| default_model_profile_id | uuid! |
| max_run_tokens | integer?1..2000000 |

新增并切换策略，default必须在白名单；暂停受影响run。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/model-policies
Authorization: Bearer <access-token>
Idempotency-Key: example-policies-create-001
If-Match: "v1"
Content-Type: application/json

{
  "mode": "local_only",
  "allowed_model_profile_ids": [
    "00000000-0000-4000-8000-000000000009"
  ],
  "default_model_profile_id": "00000000-0000-4000-8000-000000000009",
  "max_run_tokens": 300000
}
```

成功响应：HTTP 201，data模型 ProjectPolicy。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000010",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "version_no": 1,
    "mode": "local_only",
    "allowed_model_profile_ids": [
      "00000000-0000-4000-8000-000000000009"
    ],
    "default_model_profile_id": "00000000-0000-4000-8000-000000000009",
    "max_run_tokens": 300000
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.26 PUT /projects/{project_id}/knowledge-bases

权限：owner。必需Idempotency-Key。必需If-Match（父Project）。

| 参数 | 类型、必填及约束 |
|---|---|
| knowledge_base_ids | uuid[]! |

替换范围并暂停旧输入run；选择不产生授权。

请求示例：

```http
PUT /api/v1/projects/00000000-0000-4000-8000-000000000007/knowledge-bases
Authorization: Bearer <access-token>
Idempotency-Key: example-project-kbs-001
If-Match: "v1"
Content-Type: application/json

{
  "knowledge_base_ids": [
    "00000000-0000-4000-8000-000000000011"
  ]
}
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：knowledge_base_ids（array）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "knowledge_base_ids": [
      "00000000-0000-4000-8000-000000000011"
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.27 POST /knowledge-bases

权限：knowledge_admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| name | string!1..200 |
| description | string?<=2000 |

创建者获得新库manage，不能获得其他库权限。

请求示例：

```http
POST /api/v1/knowledge-bases
Authorization: Bearer <access-token>
Idempotency-Key: example-kb-create-001
Content-Type: application/json

{
  "name": "企业技术资料",
  "description": "经审核资料"
}
```

成功响应：HTTP 201，data模型 KnowledgeBase。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000011",
    "name": "企业技术资料",
    "description": "经核实的企业材料",
    "active_generation_id": null,
    "status": "active",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.28 GET /knowledge-bases

权限：已登录且库read/manage。

参数：仅路径参数及通用头、分页参数，无请求体。

按授权过滤。

请求示例：

```http
GET /api/v1/knowledge-bases?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:KnowledgeBase。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000011",
        "name": "企业技术资料",
        "description": "经核实的企业材料",
        "active_generation_id": "00000000-0000-4000-8000-000000000019",
        "status": "active",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.29 GET /knowledge-bases/{kb_id}

权限：库read/manage。

参数：仅路径参数及通用头，无请求体。

返回ETag。

请求示例：

```http
GET /api/v1/knowledge-bases/00000000-0000-4000-8000-000000000011
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 KnowledgeBase。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000011",
    "name": "企业技术资料",
    "description": "经核实的企业材料",
    "active_generation_id": "00000000-0000-4000-8000-000000000019",
    "status": "active",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.30 PATCH /knowledge-bases/{kb_id}

权限：库manage。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| name | string?1..200 |
| description | string?<=2000 |
| status | active/archived? |

归档立即停新检索并触发依赖复核。

请求示例：

```http
PATCH /api/v1/knowledge-bases/00000000-0000-4000-8000-000000000011
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "description": "已核实资料"
}
```

成功响应：HTTP 200，data模型 KnowledgeBase。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000011",
    "name": "企业技术资料",
    "description": "已核实资料",
    "active_generation_id": "00000000-0000-4000-8000-000000000019",
    "status": "active",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.31 POST /knowledge-bases/{kb_id}/index-generations

权限：库manage。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| embedding_profile_id | uuid! |
| reason | string!1..1000 |

仅内网embedding配置；新代验证后发布，失败保留旧代。

请求示例：

```http
POST /api/v1/knowledge-bases/00000000-0000-4000-8000-000000000011/index-generations
Authorization: Bearer <access-token>
Idempotency-Key: example-kb-reindex-001
Content-Type: application/json

{
  "embedding_profile_id": "00000000-0000-4000-8000-000000000901",
  "reason": "重建索引。"
}
```

成功响应：HTTP 202，data模型 Accepted:index_build:index_generations。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "index_build",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000019",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "index_generations",
      "id": "00000000-0000-4000-8000-000000000019"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.32 GET /resource-grants

权限：指定资源manage。

| 参数 | 类型、必填及约束 |
|---|---|
| Q resource_kind | knowledge_base/document! |
| Q resource_id | uuid! |

不得枚举他人资源授权。

请求示例：

```http
GET /api/v1/resource-grants?limit=20&resource_kind=knowledge_base&resource_id=00000000-0000-4000-8000-000000000011
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Grant。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000013",
        "kb_id": "00000000-0000-4000-8000-000000000011",
        "document_id": null,
        "principal_user_id": null,
        "principal_department_id": null,
        "principal_project_id": "00000000-0000-4000-8000-000000000007",
        "permission": "read",
        "expires_at": null
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.33 POST /resource-grants

权限：资源manage且有可授予权限。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| resource | {kind,id}! |
| principal | {kind,id}! |
| permission | read/manage! |
| expires_at | datetime|null? |

resource kind为knowledge_base/document，principal kind为user/department/project；更新acl_epoch。

请求示例：

```http
POST /api/v1/resource-grants
Authorization: Bearer <access-token>
Idempotency-Key: example-grants-create-001
Content-Type: application/json

{
  "resource": {
    "kind": "knowledge_base",
    "id": "00000000-0000-4000-8000-000000000011"
  },
  "principal": {
    "kind": "project",
    "id": "00000000-0000-4000-8000-000000000007"
  },
  "permission": "read",
  "expires_at": null
}
```

成功响应：HTTP 201，data模型 Grant。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000013",
    "kb_id": "00000000-0000-4000-8000-000000000011",
    "document_id": null,
    "principal_user_id": null,
    "principal_department_id": null,
    "principal_project_id": "00000000-0000-4000-8000-000000000007",
    "permission": "read",
    "expires_at": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.34 DELETE /resource-grants/{grant_id}

权限：资源manage。

参数：仅路径参数及通用头，无请求体。

同步撤权，异步清缓存/索引；授权范围内重复撤销幂等。

请求示例：

```http
DELETE /api/v1/resource-grants/00000000-0000-4000-8000-000000000013
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：revoked（boolean）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "revoked": true
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.35 POST /uploads

权限：项目owner/writer或库manage；模板需admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| purpose | source/template! |
| project_id | uuid? |
| kb_id | uuid? |
| filename | string!1..255 |
| size_bytes | integer!1..209715200 |
| sha256 | hash! |

source范围恰一；template可组织级且只接受DOCX。

请求示例：

```http
POST /api/v1/uploads
Authorization: Bearer <access-token>
Idempotency-Key: example-uploads-create-001
Content-Type: application/json

{
  "purpose": "source",
  "project_id": "00000000-0000-4000-8000-000000000007",
  "filename": "技术要求.pdf",
  "size_bytes": 1048576,
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

成功响应：HTTP 201，data模型 UploadSession。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000015",
    "state": "initiated",
    "expires_at": "2026-10-16T11:00:00Z",
    "lock_version": 1,
    "upload_url": "/api/v1/uploads/00000000-0000-4000-8000-000000000015/content",
    "max_bytes": 209715200
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.36 PUT /uploads/{upload_id}/content

权限：创建者且目标仍可写。

| 参数 | 类型、必填及约束 |
|---|---|
| Content-Type | application/octet-stream! |
| Content-Length | integer! |
| body | binary! |

大小及hash一致才成功；同会话相同内容可重PUT，不同内容UPLOAD_CONTENT_CONFLICT；过期410。

请求示例：

```http
PUT /api/v1/uploads/00000000-0000-4000-8000-000000000015/content
Authorization: Bearer <access-token>
Content-Type: application/octet-stream
Content-Length: 1048576

<二进制文件流>
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：upload_id（string）、state（string）、received_bytes（number）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "upload_id": "00000000-0000-4000-8000-000000000015",
    "state": "uploaded",
    "received_bytes": 1048576
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；特有 UPLOAD_CONTENT_CONFLICT。

### 4.37 GET /uploads/{upload_id}

权限：创建者。

参数：仅路径参数及通用头，无请求体。

查询是否完成上传。

请求示例：

```http
GET /api/v1/uploads/00000000-0000-4000-8000-000000000015
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 UploadSession。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000015",
    "state": "initiated",
    "expires_at": "2026-10-16T11:00:00Z",
    "lock_version": 1,
    "upload_url": "/api/v1/uploads/00000000-0000-4000-8000-000000000015/content",
    "max_bytes": 209715200
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.38 POST /uploads/{upload_id}/complete

权限：创建者且资源可写。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| document_id | uuid? |
| title | string?1..300 |
| kind | tender/addendum/qualification/case/technical/reference? |
| classification | internal/confidential/restricted? |
| egress_policy | EgressPolicy? |
| valid_from | datetime|null? |
| valid_until | datetime|null? |

source必须title/kind，可追加同范围document；template不创建文档，201 data=File。服务端核实hash/MIME后创建任务。

请求示例：

```http
POST /api/v1/uploads/00000000-0000-4000-8000-000000000015/complete
Authorization: Bearer <access-token>
Idempotency-Key: example-uploads-complete-001
Content-Type: application/json

{
  "title": "招标技术要求",
  "kind": "tender",
  "classification": "confidential",
  "egress_policy": {
    "schema_version": 1,
    "mode": "local_only",
    "provider_ids": []
  }
}
```

成功响应：HTTP 202，data模型 Accepted:ingest:document_versions。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "ingest",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000017",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "document_versions",
      "id": "00000000-0000-4000-8000-000000000017"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.39 GET /files/{file_id}

权限：对应资料/产物可读。

参数：仅路径参数及通用头，无请求体。

不返回object_key或S3长期地址。

请求示例：

```http
GET /api/v1/files/00000000-0000-4000-8000-000000000014
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 File。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000014",
    "original_name": "技术要求.pdf",
    "media_type": "application/pdf",
    "size_bytes": 1048576,
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "state": "ready"
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.40 GET /files/{file_id}/content

权限：资源及全部来源可读。

| 参数 | 类型、必填及约束 |
|---|---|
| Range | header string? |

二进制；支持Range返回206，无效416。每1MiB或5秒核对ACL epoch，撤权中止后续传输。

请求示例：

```http
GET /api/v1/files/00000000-0000-4000-8000-000000000014/content
Authorization: Bearer <access-token>
```

成功响应：200（Range为206），Content-Type按文件MIME，Content-Disposition带安全文件名，ETag为文件hash；响应体是二进制。

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.41 GET /documents

权限：目标范围read。

| 参数 | 类型、必填及约束 |
|---|---|
| Q project_id | uuid? |
| Q kb_id | uuid? |
| Q kind | string? |

project_id/kb_id恰一，按授权过滤。

请求示例：

```http
GET /api/v1/documents?limit=20&project_id=00000000-0000-4000-8000-000000000007
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Document。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000016",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "kb_id": null,
        "title": "招标技术要求",
        "kind": "tender",
        "current_version_id": "00000000-0000-4000-8000-000000000017",
        "classification": "confidential",
        "inherit_acl": true,
        "egress_policy": {
          "schema_version": 1,
          "mode": "local_only",
          "provider_ids": []
        },
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.42 GET /documents/{document_id}

权限：文档read。

参数：仅路径参数及通用头，无请求体。

返回当前策略和ETag。

请求示例：

```http
GET /api/v1/documents/00000000-0000-4000-8000-000000000016
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Document。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000016",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "kb_id": null,
    "title": "招标技术要求",
    "kind": "tender",
    "current_version_id": "00000000-0000-4000-8000-000000000017",
    "classification": "confidential",
    "inherit_acl": true,
    "egress_policy": {
      "schema_version": 1,
      "mode": "local_only",
      "provider_ids": []
    },
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.43 PATCH /documents/{document_id}

权限：项目owner或库manage。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| title | string?1..300 |
| inherit_acl | boolean? |
| classification | internal/confidential/restricted? |
| egress_policy | EgressPolicy? |
| reason | string?1..1000 |

策略变更必须reason；降密/放宽出网需管理授权，不能改current_version_id。

请求示例：

```http
PATCH /api/v1/documents/00000000-0000-4000-8000-000000000016
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "classification": "restricted",
  "egress_policy": {
    "schema_version": 1,
    "mode": "local_only",
    "provider_ids": []
  },
  "reason": "调整资料限制。"
}
```

成功响应：HTTP 200，data模型 Document。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000016",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "kb_id": null,
    "title": "招标技术要求",
    "kind": "tender",
    "current_version_id": "00000000-0000-4000-8000-000000000017",
    "classification": "restricted",
    "inherit_acl": true,
    "egress_policy": {
      "schema_version": 1,
      "mode": "local_only",
      "provider_ids": []
    },
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.44 DELETE /documents/{document_id}

权限：项目owner或库manage。必需If-Match（目标资源）。

参数：仅路径参数及通用头，无请求体。

先tombstone，引用过的历史资料不普通硬删除。

请求示例：

```http
DELETE /api/v1/documents/00000000-0000-4000-8000-000000000016
Authorization: Bearer <access-token>
If-Match: "v1"
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：deleted（boolean）、cleanup_pending（boolean）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "deleted": true,
    "cleanup_pending": true
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.45 GET /documents/{document_id}/versions

权限：文档read。

参数：仅路径参数及通用头、分页参数，无请求体。

历史版可审计，不自动可用于当前承诺。

请求示例：

```http
GET /api/v1/documents/00000000-0000-4000-8000-000000000016/versions?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:DocumentVersion。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000017",
        "document_id": "00000000-0000-4000-8000-000000000016",
        "file_id": "00000000-0000-4000-8000-000000000014",
        "version_no": 1,
        "status": "ready",
        "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "page_count": 60,
        "valid_until": null,
        "extraction_report": {
          "low_confidence_pages": []
        },
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.46 GET /document-versions/{version_id}

权限：文档read。

参数：仅路径参数及通用头，无请求体。

包含content_hash、解析问题和ETag。

请求示例：

```http
GET /api/v1/document-versions/00000000-0000-4000-8000-000000000017
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 DocumentVersion。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000017",
    "document_id": "00000000-0000-4000-8000-000000000016",
    "file_id": "00000000-0000-4000-8000-000000000014",
    "version_no": 1,
    "status": "ready",
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "page_count": 60,
    "valid_until": null,
    "extraction_report": {
      "low_confidence_pages": []
    },
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.47 GET /document-versions/{version_id}/chunks

权限：文档read。

参数：仅路径参数及通用头、分页参数，无请求体。

按ordinal游标，原文按指定版本定位。

请求示例：

```http
GET /api/v1/document-versions/00000000-0000-4000-8000-000000000017/chunks?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Chunk。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000018",
        "document_version_id": "00000000-0000-4000-8000-000000000017",
        "text": "系统须支持按角色配置权限。",
        "locator": {
          "schema_version": 1,
          "format": "pdf",
          "page_start": 12,
          "page_end": 12,
          "block_id": "p12-b3"
        },
        "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.48 POST /document-versions/{version_id}/corrections

权限：owner/writer或库manage。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| corrections | {block_id,replacement_text}[]! |
| note | string!1..2000 |
| expected_content_hash | hash! |

新提取版本，保留原OCR；空corrections表示人工确认无误，也创建带复核记录的新版本。

请求示例：

```http
POST /api/v1/document-versions/00000000-0000-4000-8000-000000000017/corrections
Authorization: Bearer <access-token>
Idempotency-Key: example-versions-correct-001
If-Match: "v1"
Content-Type: application/json

{
  "corrections": [
    {
      "block_id": "p12-b3",
      "replacement_text": "系统须支持按角色配置权限。"
    }
  ],
  "note": "已核对原件。",
  "expected_content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

成功响应：HTTP 202，data模型 Accepted:ingest:document_versions。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "ingest",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000904",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "document_versions",
      "id": "00000000-0000-4000-8000-000000000904"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.49 POST /projects/{project_id}/knowledge-search

权限：owner/writer/reviewer且资料read。

| 参数 | 类型、必填及约束 |
|---|---|
| query | string!1..2000 |
| knowledge_base_ids | uuid[]? |
| include_project_documents | boolean? |
| top_k | integer?1..20 |

仅已选范围；不接收expr/collection；生成上下文仍最多12条。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/knowledge-search
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "query": "权限与审计方案",
  "knowledge_base_ids": [
    "00000000-0000-4000-8000-000000000011"
  ],
  "include_project_documents": true,
  "top_k": 12
}
```

成功响应：HTTP 200，data模型 SearchResult。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "hits": [
      {
        "chunk_id": "00000000-0000-4000-8000-000000000018",
        "document_version_id": "00000000-0000-4000-8000-000000000017",
        "text": "系统须支持按角色配置权限。",
        "locator": {
          "schema_version": 1,
          "format": "pdf",
          "page_start": 12,
          "page_end": 12,
          "block_id": "p12-b3"
        },
        "rank": 1,
        "usage_kind": "requirement"
      }
    ],
    "generation_ids": [
      "00000000-0000-4000-8000-000000000019"
    ],
    "warnings": []
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.50 GET /templates

权限：已登录。

| 参数 | 类型、必填及约束 |
|---|---|
| Q industry | general/construction/it? |

只列发布模板。

请求示例：

```http
GET /api/v1/templates?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Template。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000025",
        "code": "it-standard",
        "name": "IT技术标模板",
        "industry": "it",
        "active_version_id": "00000000-0000-4000-8000-000000000026",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.51 POST /templates

权限：system_admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| code | string!1..80 |
| name | string!1..200 |
| industry | general/construction/it! |

创建系列，尚未发布。

请求示例：

```http
POST /api/v1/templates
Authorization: Bearer <access-token>
Idempotency-Key: example-templates-create-001
Content-Type: application/json

{
  "code": "it-standard",
  "name": "IT技术标模板",
  "industry": "it"
}
```

成功响应：HTTP 201，data模型 Template。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000025",
    "code": "it-standard",
    "name": "IT技术标模板",
    "industry": "it",
    "active_version_id": null,
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.52 POST /templates/{template_id}/versions

权限：system_admin。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| file_id | uuid! |
| manifest | TemplateManifest! |

仅接收部署流水线已验收制品；服务端校验报告可信签名/登记与文件hash，不信任客户端status。发布后固定版本。

请求示例：

```http
POST /api/v1/templates/00000000-0000-4000-8000-000000000025/versions
Authorization: Bearer <access-token>
Idempotency-Key: example-templates-version-001
Content-Type: application/json

{
  "file_id": "00000000-0000-4000-8000-000000000902",
  "manifest": {
    "schema_version": 1,
    "slots": [
      "title",
      "toc",
      "chapters"
    ],
    "styles": {
      "body_font": "SimSun",
      "body_size_pt": 12
    },
    "numbering": "decimal",
    "page_setup": {
      "size": "A4"
    },
    "citation_appendix": false,
    "font_bundle_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "validation": {
      "status": "passed",
      "report_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }
}
```

成功响应：HTTP 201，data模型 TemplateVersion。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000026",
    "template_id": "00000000-0000-4000-8000-000000000025",
    "version_no": 1,
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.53 POST /projects/{project_id}/requirement-sets

权限：owner/writer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| document_version_ids | uuid[]!1..100 |
| supersedes_id | uuid|null? |
| instructions | string?<=2000 |

创建候选版本，旧确认集在新集确认前继续有效。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/requirement-sets
Authorization: Bearer <access-token>
Idempotency-Key: example-requirements-analyze-001
Content-Type: application/json

{
  "document_version_ids": [
    "00000000-0000-4000-8000-000000000017"
  ],
  "supersedes_id": null,
  "instructions": "提取评分点与强制技术要求。"
}
```

成功响应：HTTP 202，data模型 Accepted:analyze:requirement_sets。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "analyze",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000021",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "requirement_sets",
      "id": "00000000-0000-4000-8000-000000000021"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.54 GET /projects/{project_id}/requirement-sets

权限：项目成员且来源read。

参数：仅路径参数及通用头、分页参数，无请求体。

只返回可访问来源的要求集。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/requirement-sets?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:RequirementSet。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000021",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "version_no": 1,
        "supersedes_id": null,
        "status": "ready",
        "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "diff_summary": {
          "added": 1,
          "changed": 0,
          "removed": 0
        },
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.55 GET /requirement-sets/{set_id}

权限：项目成员且来源read。

参数：仅路径参数及通用头，无请求体。

返回差异和ETag。

请求示例：

```http
GET /api/v1/requirement-sets/00000000-0000-4000-8000-000000000021
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 RequirementSet。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000021",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "version_no": 1,
    "supersedes_id": null,
    "status": "ready",
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "diff_summary": {
      "added": 1,
      "changed": 0,
      "removed": 0
    },
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.56 GET /requirement-sets/{set_id}/requirements

权限：项目成员且来源read。

| 参数 | 类型、必填及约束 |
|---|---|
| Q scope | technical/out_of_scope/needs_human? |
| Q mandatory | boolean? |

不隐式省略范围外条款。

请求示例：

```http
GET /api/v1/requirement-sets/00000000-0000-4000-8000-000000000021/requirements?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Requirement。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000023",
        "code": "T-001",
        "text": "系统须支持按角色配置权限。",
        "category": "technical",
        "scope": "technical",
        "mandatory": true,
        "source_chunk_id": "00000000-0000-4000-8000-000000000018",
        "locator": {
          "schema_version": 1,
          "format": "pdf",
          "page_start": 12,
          "page_end": 12
        },
        "clarification": null,
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.57 POST /requirement-sets/{set_id}/requirements

权限：owner/writer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| code | string!<=80 |
| text | string!<=20000 |
| category | string! |
| scope | technical/out_of_scope/needs_human! |
| mandatory | boolean! |
| source_chunk_id | uuid! |
| locator | Locator! |
| clarification | string|null? |

只允许draft/ready；category枚举见模型；来源须属于该集。

请求示例：

```http
POST /api/v1/requirement-sets/00000000-0000-4000-8000-000000000021/requirements
Authorization: Bearer <access-token>
Idempotency-Key: example-requirements-add-001
Content-Type: application/json

{
  "code": "T-001",
  "text": "系统须支持按角色配置权限。",
  "category": "technical",
  "scope": "technical",
  "mandatory": true,
  "source_chunk_id": "00000000-0000-4000-8000-000000000018",
  "locator": {
    "schema_version": 1,
    "format": "pdf",
    "page_start": 12,
    "page_end": 12
  }
}
```

成功响应：HTTP 201，data模型 Requirement。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000023",
    "code": "T-001",
    "text": "系统须支持按角色配置权限。",
    "category": "technical",
    "scope": "technical",
    "mandatory": true,
    "source_chunk_id": "00000000-0000-4000-8000-000000000018",
    "locator": {
      "schema_version": 1,
      "format": "pdf",
      "page_start": 12,
      "page_end": 12
    },
    "clarification": null,
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.58 PATCH /requirements/{requirement_id}

权限：owner/writer。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| text | string?<=20000 |
| category | string? |
| scope | string? |
| mandatory | boolean? |
| clarification | string|null? |
| source_chunk_id | uuid? |
| locator | Locator? |

confirmed不可改，须新要求版本。

请求示例：

```http
PATCH /api/v1/requirements/00000000-0000-4000-8000-000000000023
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "clarification": "采用角色与数据范围联合授权。"
}
```

成功响应：HTTP 200，data模型 Requirement。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000023",
    "code": "T-001",
    "text": "系统须支持按角色配置权限。",
    "category": "technical",
    "scope": "technical",
    "mandatory": true,
    "source_chunk_id": "00000000-0000-4000-8000-000000000018",
    "locator": {
      "schema_version": 1,
      "format": "pdf",
      "page_start": 12,
      "page_end": 12
    },
    "clarification": "采用角色与数据范围联合授权。",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.59 GET /requirement-sets/{set_id}/scoring-items

权限：项目成员且来源read。

参数：仅路径参数及通用头、分页参数，无请求体。

未知分值为null。

请求示例：

```http
GET /api/v1/requirement-sets/00000000-0000-4000-8000-000000000021/scoring-items?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:ScoringItem。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000024",
        "requirement_id": "00000000-0000-4000-8000-000000000023",
        "title": "权限方案",
        "max_score": "5.00",
        "criteria": {
          "levels": [
            {
              "score": "5.00",
              "condition": "响应完整"
            }
          ]
        },
        "source_chunk_id": "00000000-0000-4000-8000-000000000018",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.60 POST /requirement-sets/{set_id}/scoring-items

权限：owner/writer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| requirement_id | uuid! |
| title | string!<=300 |
| max_score | decimal|null! |
| criteria | object! |
| source_chunk_id | uuid! |

只允许未确认集，分值非负，不强制归一到100。

请求示例：

```http
POST /api/v1/requirement-sets/00000000-0000-4000-8000-000000000021/scoring-items
Authorization: Bearer <access-token>
Idempotency-Key: example-scoring-add-001
Content-Type: application/json

{
  "requirement_id": "00000000-0000-4000-8000-000000000023",
  "title": "权限方案",
  "max_score": "5.00",
  "criteria": {
    "levels": [
      {
        "score": "5.00",
        "condition": "响应完整"
      }
    ]
  },
  "source_chunk_id": "00000000-0000-4000-8000-000000000018"
}
```

成功响应：HTTP 201，data模型 ScoringItem。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000024",
    "requirement_id": "00000000-0000-4000-8000-000000000023",
    "title": "权限方案",
    "max_score": "5.00",
    "criteria": {
      "levels": [
        {
          "score": "5.00",
          "condition": "响应完整"
        }
      ]
    },
    "source_chunk_id": "00000000-0000-4000-8000-000000000018",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.61 PATCH /scoring-items/{scoring_id}

权限：owner/writer。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| title | string?<=300 |
| max_score | decimal|null? |
| criteria | object? |

要求确认后不可原地改。

请求示例：

```http
PATCH /api/v1/scoring-items/00000000-0000-4000-8000-000000000024
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "max_score": "5.00"
}
```

成功响应：HTTP 200，data模型 ScoringItem。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000024",
    "requirement_id": "00000000-0000-4000-8000-000000000023",
    "title": "权限方案",
    "max_score": "5.00",
    "criteria": {
      "levels": [
        {
          "score": "5.00",
          "condition": "响应完整"
        }
      ]
    },
    "source_chunk_id": "00000000-0000-4000-8000-000000000018",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.62 POST /requirement-sets/{set_id}/confirm

权限：owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| expected_content_hash | hash! |
| note | string!<=2000 |

未解决needs_human/低质量来源返回INPUT_NOT_READY；确认后传播失效。

请求示例：

```http
POST /api/v1/requirement-sets/00000000-0000-4000-8000-000000000021/confirm
Authorization: Bearer <access-token>
Idempotency-Key: example-requirements-confirm-001
If-Match: "v1"
Content-Type: application/json

{
  "expected_content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "note": "已核对招标原件与补遗。"
}
```

成功响应：HTTP 200，data模型 RequirementSet。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000021",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "version_no": 1,
    "supersedes_id": null,
    "status": "confirmed",
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "diff_summary": {
      "added": 1,
      "changed": 0,
      "removed": 0
    },
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；特有 INPUT_NOT_READY。

### 4.63 POST /projects/{project_id}/outlines

权限：owner/writer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| requirement_set_id | uuid! |
| template_version_id | uuid! |
| base_outline_id | uuid|null? |
| instructions | string?<=2000 |

须当前确认要求，生成候选不能自动确认。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/outlines
Authorization: Bearer <access-token>
Idempotency-Key: example-outlines-create-001
Content-Type: application/json

{
  "requirement_set_id": "00000000-0000-4000-8000-000000000021",
  "template_version_id": "00000000-0000-4000-8000-000000000026",
  "instructions": "优先覆盖评分项。"
}
```

成功响应：HTTP 202，data模型 Accepted:outline:outlines。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "outline",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000027",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "outlines",
      "id": "00000000-0000-4000-8000-000000000027"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.64 GET /projects/{project_id}/outlines

权限：项目成员且来源read。

参数：仅路径参数及通用头、分页参数，无请求体。

按版本倒序。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/outlines?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Outline。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000027",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "requirement_set_id": "00000000-0000-4000-8000-000000000021",
        "template_version_id": "00000000-0000-4000-8000-000000000026",
        "version_no": 1,
        "status": "ready",
        "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "lock_version": 1,
        "nodes": [
          {
            "id": "00000000-0000-4000-8000-000000000028",
            "parent_id": null,
            "chapter_id": "00000000-0000-4000-8000-000000000029",
            "position": 1,
            "title": "总体技术方案",
            "target_words": 3000,
            "requirement_ids": [
              "00000000-0000-4000-8000-000000000023"
            ],
            "instructions": "逐条响应技术要求。"
          }
        ]
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.65 GET /outlines/{outline_id}

权限：项目成员且来源read。

参数：仅路径参数及通用头，无请求体。

含节点树和摘要。

请求示例：

```http
GET /api/v1/outlines/00000000-0000-4000-8000-000000000027
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Outline。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000027",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "template_version_id": "00000000-0000-4000-8000-000000000026",
    "version_no": 1,
    "status": "ready",
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "lock_version": 1,
    "nodes": [
      {
        "id": "00000000-0000-4000-8000-000000000028",
        "parent_id": null,
        "chapter_id": "00000000-0000-4000-8000-000000000029",
        "position": 1,
        "title": "总体技术方案",
        "target_words": 3000,
        "requirement_ids": [
          "00000000-0000-4000-8000-000000000023"
        ],
        "instructions": "逐条响应技术要求。"
      }
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.66 PATCH /outlines/{outline_id}

权限：owner/writer。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| nodes | OutlineNodeInput[]!max200叶 |

仅draft/ready，完整替换；已有id来自本候选树，新节点不传id由服务端分配；禁止环，关联条款同集。

请求示例：

```http
PATCH /api/v1/outlines/00000000-0000-4000-8000-000000000027
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "nodes": [
    {
      "parent_id": null,
      "position": 1,
      "title": "总体技术方案",
      "target_words": 3000,
      "requirement_ids": [
        "00000000-0000-4000-8000-000000000023"
      ],
      "instructions": "覆盖评分点。"
    }
  ]
}
```

成功响应：HTTP 200，data模型 Outline。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000027",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "template_version_id": "00000000-0000-4000-8000-000000000026",
    "version_no": 1,
    "status": "ready",
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "lock_version": 2,
    "nodes": [
      {
        "parent_id": null,
        "position": 1,
        "title": "总体技术方案",
        "target_words": 3000,
        "requirement_ids": [
          "00000000-0000-4000-8000-000000000023"
        ],
        "instructions": "覆盖评分点。"
      }
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.67 POST /outlines/{outline_id}/confirm

权限：owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| expected_content_hash | hash! |
| note | string!<=2000 |

对齐稳定章节，保留旧正文，暂停活动run并触发复核。

请求示例：

```http
POST /api/v1/outlines/00000000-0000-4000-8000-000000000027/confirm
Authorization: Bearer <access-token>
Idempotency-Key: example-outlines-confirm-001
If-Match: "v1"
Content-Type: application/json

{
  "expected_content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "note": "确认章节和评分点对应。"
}
```

成功响应：HTTP 200，data模型 Outline。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000027",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "template_version_id": "00000000-0000-4000-8000-000000000026",
    "version_no": 1,
    "status": "confirmed",
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "lock_version": 2,
    "nodes": [
      {
        "id": "00000000-0000-4000-8000-000000000028",
        "parent_id": null,
        "chapter_id": "00000000-0000-4000-8000-000000000029",
        "position": 1,
        "title": "总体技术方案",
        "target_words": 3000,
        "requirement_ids": [
          "00000000-0000-4000-8000-000000000023"
        ],
        "instructions": "逐条响应技术要求。"
      }
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.68 GET /projects/{project_id}/chapters

权限：项目成员。

参数：仅路径参数及通用头、分页参数，无请求体。

默认当前active大纲，按position。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/chapters?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Chapter。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000029",
        "title": "总体技术方案",
        "position": 1,
        "status": "draft",
        "current_version_id": "00000000-0000-4000-8000-000000000030",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.69 GET /chapters/{chapter_id}

权限：项目成员。

参数：仅路径参数及通用头，无请求体。

仅工作区元数据，正文另取版本。

请求示例：

```http
GET /api/v1/chapters/00000000-0000-4000-8000-000000000029
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Chapter。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000029",
    "title": "总体技术方案",
    "position": 1,
    "status": "draft",
    "current_version_id": "00000000-0000-4000-8000-000000000030",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.70 GET /chapters/{chapter_id}/versions

权限：项目成员及全部来源read。

参数：仅路径参数及通用头、分页参数，无请求体。

逐版本校验谱系。

请求示例：

```http
GET /api/v1/chapters/00000000-0000-4000-8000-000000000029/versions?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:ChapterVersion。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000030",
        "chapter_id": "00000000-0000-4000-8000-000000000029",
        "version_no": 1,
        "submitted_by": "00000000-0000-4000-8000-000000000003",
        "content": {
          "schema_version": 1,
          "blocks": [
            {
              "block_id": "b1",
              "type": "paragraph",
              "text": "本项目拟采用角色与数据范围联合授权。"
            }
          ]
        },
        "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "source_version_ids": [
          "00000000-0000-4000-8000-000000000017"
        ],
        "citations": []
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.71 GET /chapter-versions/{version_id}

权限：项目成员及全部来源read。

参数：仅路径参数及通用头，无请求体。

任一来源撤权拒绝整版ACCESS_DEPENDENCY_REVOKED。

请求示例：

```http
GET /api/v1/chapter-versions/00000000-0000-4000-8000-000000000030
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 ChapterVersion。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000030",
    "chapter_id": "00000000-0000-4000-8000-000000000029",
    "version_no": 1,
    "submitted_by": "00000000-0000-4000-8000-000000000003",
    "content": {
      "schema_version": 1,
      "blocks": [
        {
          "block_id": "b1",
          "type": "paragraph",
          "text": "本项目拟采用角色与数据范围联合授权。"
        }
      ]
    },
    "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "source_version_ids": [
      "00000000-0000-4000-8000-000000000017"
    ],
    "citations": []
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；特有 ACCESS_DEPENDENCY_REVOKED。

### 4.72 PATCH /chapters/{chapter_id}

权限：owner/writer。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| base_version_id | uuid|null! |
| content | ContentDocument! |
| citations | CitationInput[]! |
| source_version_ids | uuid[]! |
| change_note | string!<=1000 |

新增版本并保留谱系；旧审核失效，后续needs_review。finalized先reopen。返回chapter和version，ETag取chapter。

请求示例：

```http
PATCH /api/v1/chapters/00000000-0000-4000-8000-000000000029
Authorization: Bearer <access-token>
If-Match: "v1"
Content-Type: application/json

{
  "base_version_id": "00000000-0000-4000-8000-000000000030",
  "content": {
    "schema_version": 1,
    "blocks": [
      {
        "block_id": "b1",
        "type": "paragraph",
        "text": "本项目拟采用角色与数据范围联合授权。"
      }
    ]
  },
  "citations": [],
  "source_version_ids": [
    "00000000-0000-4000-8000-000000000017"
  ],
  "change_note": "补充技术方案。"
}
```

成功响应：HTTP 200，data模型 ChapterEdit。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "chapter": {
      "id": "00000000-0000-4000-8000-000000000029",
      "title": "总体技术方案",
      "position": 1,
      "status": "draft",
      "current_version_id": "00000000-0000-4000-8000-000000000905",
      "lock_version": 2
    },
    "version": {
      "id": "00000000-0000-4000-8000-000000000905",
      "chapter_id": "00000000-0000-4000-8000-000000000029",
      "version_no": 2,
      "submitted_by": "00000000-0000-4000-8000-000000000003",
      "content": {
        "schema_version": 1,
        "blocks": [
          {
            "block_id": "b1",
            "type": "paragraph",
            "text": "本项目拟采用角色与数据范围联合授权。"
          }
        ]
      },
      "content_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "source_version_ids": [
        "00000000-0000-4000-8000-000000000017"
      ],
      "citations": []
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.73 POST /chapters/{chapter_id}/reviews

权限：owner/writer。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| chapter_version_id | uuid! |
| assigned_to | uuid|null? |

前置章均批准；同版本pending返回既有审核。自动提交复用此用例。

请求示例：

```http
POST /api/v1/chapters/00000000-0000-4000-8000-000000000029/reviews
Authorization: Bearer <access-token>
Idempotency-Key: example-chapters-review-001
If-Match: "v1"
Content-Type: application/json

{
  "chapter_version_id": "00000000-0000-4000-8000-000000000030",
  "assigned_to": null
}
```

成功响应：HTTP 201，data模型 Review。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000034",
    "run_id": "00000000-0000-4000-8000-000000000041",
    "chapter_version_id": "00000000-0000-4000-8000-000000000030",
    "submitted_by": "00000000-0000-4000-8000-000000000003",
    "assigned_to": null,
    "status": "pending",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.74 GET /projects/{project_id}/reviews

权限：owner/writer/reviewer。

| 参数 | 类型、必填及约束 |
|---|---|
| Q status | review_status? |

查看和审批正文仍检查来源。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/reviews?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Review。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000034",
        "run_id": "00000000-0000-4000-8000-000000000041",
        "chapter_version_id": "00000000-0000-4000-8000-000000000030",
        "submitted_by": "00000000-0000-4000-8000-000000000003",
        "assigned_to": null,
        "status": "pending",
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.75 GET /reviews/{review_id}

权限：项目成员。

参数：仅路径参数及通用头，无请求体。

含目标版本和ETag。

请求示例：

```http
GET /api/v1/reviews/00000000-0000-4000-8000-000000000034
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Review。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000034",
    "run_id": "00000000-0000-4000-8000-000000000041",
    "chapter_version_id": "00000000-0000-4000-8000-000000000030",
    "submitted_by": "00000000-0000-4000-8000-000000000003",
    "assigned_to": null,
    "status": "pending",
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.76 POST /reviews/{review_id}/decisions

权限：reviewer且非submitted_by。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| chapter_version_id | uuid! |
| version_hash | hash! |
| decision | approved/rejected! |
| comment | string!1..4000 |

旧版REVIEW_STALE、自审REVIEW_SELF_FORBIDDEN。通过异步推进；退回waiting_input，由编写人决定修订。

请求示例：

```http
POST /api/v1/reviews/00000000-0000-4000-8000-000000000034/decisions
Authorization: Bearer <access-token>
Idempotency-Key: example-reviews-decide-001
If-Match: "v1"
Content-Type: application/json

{
  "chapter_version_id": "00000000-0000-4000-8000-000000000030",
  "version_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "decision": "approved",
  "comment": "已核对要求及证据。"
}
```

成功响应：HTTP 200，data模型 Review。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000034",
    "run_id": "00000000-0000-4000-8000-000000000041",
    "chapter_version_id": "00000000-0000-4000-8000-000000000030",
    "submitted_by": "00000000-0000-4000-8000-000000000003",
    "assigned_to": null,
    "status": "approved",
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；特有 REVIEW_STALE、REVIEW_SELF_FORBIDDEN。

### 4.77 GET /projects/{project_id}/response-matrix

权限：项目成员及正文来源read。

| 参数 | 类型、必填及约束 |
|---|---|
| Q requirement_set_id | uuid? |
| Q status | covered/partial/missing/not_applicable? |

默认当前集，缺失条款也有missing行。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/response-matrix?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:ResponseMapping。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000033",
        "requirement_id": "00000000-0000-4000-8000-000000000023",
        "chapter_version_id": "00000000-0000-4000-8000-000000000030",
        "status": "covered",
        "response_summary": "见总体技术方案。",
        "citation_ids": [],
        "reason": null,
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.78 PUT /requirements/{requirement_id}/response-mappings

权限：owner/writer。必需Idempotency-Key。必需If-Match（父Project）。

| 参数 | 类型、必填及约束 |
|---|---|
| chapter_version_id | uuid|null! |
| status | covered/partial/missing/not_applicable! |
| response_summary | string!<=4000 |
| citation_ids | uuid[]! |
| reason | string|null? |

父Project ETag，复合键upsert；missing/not_applicable必须reason，强制项不能靠状态绕过检查。

请求示例：

```http
PUT /api/v1/requirements/00000000-0000-4000-8000-000000000023/response-mappings
Authorization: Bearer <access-token>
Idempotency-Key: example-response-put-001
If-Match: "v1"
Content-Type: application/json

{
  "chapter_version_id": "00000000-0000-4000-8000-000000000030",
  "status": "covered",
  "response_summary": "见总体技术方案。",
  "citation_ids": [],
  "reason": null
}
```

成功响应：HTTP 200，data模型 ResponseMapping。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000033",
    "requirement_id": "00000000-0000-4000-8000-000000000023",
    "chapter_version_id": "00000000-0000-4000-8000-000000000030",
    "status": "covered",
    "response_summary": "见总体技术方案。",
    "citation_ids": [],
    "reason": null,
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.79 DELETE /requirements/{requirement_id}

权限：owner/writer。必需If-Match（目标资源）。

参数：仅路径参数及通用头，无请求体。

仅draft/ready且无评分项引用；confirmed返回IMMUTABLE_VERSION，删除留审计。

请求示例：

```http
DELETE /api/v1/requirements/00000000-0000-4000-8000-000000000023
Authorization: Bearer <access-token>
If-Match: "v1"
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：removed（boolean）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "removed": true
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；特有 IMMUTABLE_VERSION。

### 4.80 DELETE /scoring-items/{scoring_id}

权限：owner/writer。必需If-Match（目标资源）。

参数：仅路径参数及通用头，无请求体。

仅未确认集；误提取原文仍保留。

请求示例：

```http
DELETE /api/v1/scoring-items/00000000-0000-4000-8000-000000000024
Authorization: Bearer <access-token>
If-Match: "v1"
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：removed（boolean）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "removed": true
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；状态或资源前置条件不满足返回409，详细原因见code。

### 4.81 POST /projects/{project_id}/runs

权限：owner/writer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| requirement_set_id | uuid! |
| outline_id | uuid! |
| expected_project_version | integer! |
| instructions | string?<=4000 |
| budget_tokens | integer?1..2000000 |

每项目一活动run；writer不得超过策略额度，从首个未批准章开始。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/runs
Authorization: Bearer <access-token>
Idempotency-Key: example-runs-create-001
Content-Type: application/json

{
  "requirement_set_id": "00000000-0000-4000-8000-000000000021",
  "outline_id": "00000000-0000-4000-8000-000000000027",
  "expected_project_version": 1,
  "instructions": "突出评分项。",
  "budget_tokens": 300000
}
```

成功响应：HTTP 202，data模型 Run。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000041",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "status": "queued",
    "wait_reason": null,
    "current_chapter_id": "00000000-0000-4000-8000-000000000029",
    "workflow_version": "technical-bid-v1",
    "budget_tokens": 300000,
    "spent_tokens": 0,
    "reserved_tokens": 0,
    "lock_version": 1,
    "error": null,
    "input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "last_event_seq": 1,
    "events_retained_from": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.82 GET /projects/{project_id}/runs

权限：项目成员。

| 参数 | 类型、必填及约束 |
|---|---|
| Q status | run_status? |

仅状态元数据，不返回checkpoint。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/runs?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Run。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000041",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "status": "queued",
        "wait_reason": null,
        "current_chapter_id": "00000000-0000-4000-8000-000000000029",
        "workflow_version": "technical-bid-v1",
        "budget_tokens": 300000,
        "spent_tokens": 0,
        "reserved_tokens": 0,
        "lock_version": 1,
        "error": null,
        "input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "last_event_seq": 1,
        "events_retained_from": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.83 GET /runs/{run_id}

权限：项目成员。

参数：仅路径参数及通用头，无请求体。

包含等待原因、用量、输入hash。

请求示例：

```http
GET /api/v1/runs/00000000-0000-4000-8000-000000000041
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Run。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000041",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "status": "queued",
    "wait_reason": null,
    "current_chapter_id": "00000000-0000-4000-8000-000000000029",
    "workflow_version": "technical-bid-v1",
    "budget_tokens": 300000,
    "spent_tokens": 0,
    "reserved_tokens": 0,
    "lock_version": 1,
    "error": null,
    "input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "last_event_seq": 1,
    "events_retained_from": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.84 POST /runs/{run_id}/resume

权限：发起人或owner；增预算只owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | revise/inputs_updated/evidence_updated/budget_increased! |
| expected_input_snapshot_hash | hash! |
| expected_project_version | integer! |
| instructions | string?<=4000 |
| new_budget_tokens | integer? |

仅waiting_input；budget_increased必须更大额度≤组织上限；服务端重建授权上下文，不加载已撤权旧内容。原主体停用须取消后新建。

请求示例：

```http
POST /api/v1/runs/00000000-0000-4000-8000-000000000041/resume
Authorization: Bearer <access-token>
Idempotency-Key: example-runs-resume-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "revise",
  "expected_input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "expected_project_version": 1,
  "instructions": "按审核意见补充。"
}
```

成功响应：HTTP 202，data模型 Run。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000041",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "status": "queued",
    "wait_reason": null,
    "current_chapter_id": "00000000-0000-4000-8000-000000000029",
    "workflow_version": "technical-bid-v1",
    "budget_tokens": 300000,
    "spent_tokens": 0,
    "reserved_tokens": 0,
    "lock_version": 2,
    "error": null,
    "input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "last_event_seq": 1,
    "events_retained_from": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.85 POST /runs/{run_id}/retry

权限：发起人或owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | string!1..1000 |

仅failed且retryable、无新活动run、checkpoint未过期；dispatch_no递增。

请求示例：

```http
POST /api/v1/runs/00000000-0000-4000-8000-000000000041/retry
Authorization: Bearer <access-token>
Idempotency-Key: example-runs-retry-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "依赖恢复后重试。"
}
```

成功响应：HTTP 202，data模型 Run。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000041",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "status": "queued",
    "wait_reason": null,
    "current_chapter_id": "00000000-0000-4000-8000-000000000029",
    "workflow_version": "technical-bid-v1",
    "budget_tokens": 300000,
    "spent_tokens": 0,
    "reserved_tokens": 0,
    "lock_version": 2,
    "error": null,
    "input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "last_event_seq": 1,
    "events_retained_from": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.86 POST /runs/{run_id}/cancel

权限：发起人或owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | string!1..1000 |

running先cancel_requested；queued/等待态立即200 cancelled。pending审核stale；成功run返回RUN_TERMINAL。外部调用可能仍计费。

请求示例：

```http
POST /api/v1/runs/00000000-0000-4000-8000-000000000041/cancel
Authorization: Bearer <access-token>
Idempotency-Key: example-runs-cancel-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "更新资料。"
}
```

成功响应：HTTP 202，data模型 Run。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000041",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "status": "cancel_requested",
    "wait_reason": null,
    "current_chapter_id": "00000000-0000-4000-8000-000000000029",
    "workflow_version": "technical-bid-v1",
    "budget_tokens": 300000,
    "spent_tokens": 0,
    "reserved_tokens": 0,
    "lock_version": 2,
    "error": null,
    "input_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "last_event_seq": 1,
    "events_retained_from": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；特有 RUN_TERMINAL。

### 4.87 GET /runs/{run_id}/events

权限：项目成员，连接持续授权。

| 参数 | 类型、必填及约束 |
|---|---|
| Last-Event-ID | header integer? |
| Q after | integer? |

两种游标同时给且不一致422；事件不含正文，协议见第5节。

请求示例：

```http
GET /api/v1/runs/00000000-0000-4000-8000-000000000041/events?after=1
Authorization: Bearer <access-token>
```

成功响应：200 text/event-stream，逐事件格式见第5节。

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.88 GET /runs/{run_id}/usage

权限：owner或发起人。

参数：仅路径参数及通用头，无请求体。

金额decimal字符串或null，未知不能按0合计。

请求示例：

```http
GET /api/v1/runs/00000000-0000-4000-8000-000000000041/usage
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：run_id（string）、budget_tokens（number）、spent_tokens（number）、reserved_tokens（number）、calls（array）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "run_id": "00000000-0000-4000-8000-000000000041",
    "budget_tokens": 300000,
    "spent_tokens": 12000,
    "reserved_tokens": 0,
    "calls": [
      {
        "profile_id": "00000000-0000-4000-8000-000000000009",
        "input_tokens": 10000,
        "output_tokens": 2000,
        "cost_amount": null,
        "currency": null,
        "status": "succeeded"
      }
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.89 GET /jobs

权限：项目或库可读。

| 参数 | 类型、必填及约束 |
|---|---|
| Q project_id | uuid? |
| Q kb_id | uuid? |
| Q status | job_status? |
| Q kind | string? |

project/kb恰一，错误不泄露原文。

请求示例：

```http
GET /api/v1/jobs?limit=20&project_id=00000000-0000-4000-8000-000000000007
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Job。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000042",
        "kind": "ingest",
        "status": "queued",
        "target_id": "00000000-0000-4000-8000-000000000017",
        "progress": 0,
        "attempt": 0,
        "lock_version": 1,
        "error": null
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.90 GET /jobs/{job_id}

权限：目标范围可读。

参数：仅路径参数及通用头，无请求体。

轮询2秒退避至10秒。

请求示例：

```http
GET /api/v1/jobs/00000000-0000-4000-8000-000000000042
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Job。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000042",
    "kind": "ingest",
    "status": "queued",
    "target_id": "00000000-0000-4000-8000-000000000017",
    "progress": 0,
    "attempt": 0,
    "lock_version": 1,
    "error": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.91 POST /jobs/{job_id}/retry

权限：发起人或owner/库manage。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | string!1..1000 |

failed且retryable；attempt不清零，最多5次。

请求示例：

```http
POST /api/v1/jobs/00000000-0000-4000-8000-000000000042/retry
Authorization: Bearer <access-token>
Idempotency-Key: example-jobs-retry-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "依赖已恢复。"
}
```

成功响应：HTTP 202，data模型 Job。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000042",
    "kind": "ingest",
    "status": "queued",
    "target_id": "00000000-0000-4000-8000-000000000017",
    "progress": 0,
    "attempt": 0,
    "lock_version": 2,
    "error": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.92 POST /jobs/{job_id}/cancel

权限：发起人或owner/库manage。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | string!1..1000 |

等待态可立即200 cancelled；未发布资料保持不可用，旧current版本保留。

请求示例：

```http
POST /api/v1/jobs/00000000-0000-4000-8000-000000000042/cancel
Authorization: Bearer <access-token>
Idempotency-Key: example-jobs-cancel-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "取消本次入库。"
}
```

成功响应：HTTP 202，data模型 Job。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000042",
    "kind": "ingest",
    "status": "cancel_requested",
    "target_id": "00000000-0000-4000-8000-000000000017",
    "progress": 0,
    "attempt": 0,
    "lock_version": 2,
    "error": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.93 POST /projects/{project_id}/checks

权限：owner/writer/reviewer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| chapter_version_id | uuid|null? |
| expected_snapshot_hash | hash! |

空章节为全文，先冻结输入，旧检查不能用于新快照。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/checks
Authorization: Bearer <access-token>
Idempotency-Key: example-checks-create-001
Content-Type: application/json

{
  "chapter_version_id": null,
  "expected_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

成功响应：HTTP 202，data模型 Accepted:check:checks。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "check",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000036",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "checks",
      "id": "00000000-0000-4000-8000-000000000036"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.94 GET /projects/{project_id}/checks

权限：项目成员及来源read。

参数：仅路径参数及通用头、分页参数，无请求体。

按创建倒序。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/checks?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Check。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000036",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "chapter_version_id": null,
        "status": "completed",
        "snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "summary": {
          "blockers": 0,
          "warnings": 0,
          "mandatory_coverage": 1
        },
        "lock_version": 1
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.95 GET /checks/{check_id}

权限：项目成员及来源read。

参数：仅路径参数及通用头，无请求体。

返回hash和统计，问题分页。

请求示例：

```http
GET /api/v1/checks/00000000-0000-4000-8000-000000000036
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Check。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000036",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "chapter_version_id": null,
    "status": "completed",
    "snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "summary": {
      "blockers": 0,
      "warnings": 0,
      "mandatory_coverage": 1
    },
    "lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.96 GET /checks/{check_id}/findings

权限：项目成员及来源read。

| 参数 | 类型、必填及约束 |
|---|---|
| Q severity | blocker/warning/info? |

问题同样继承正文来源权限。

请求示例：

```http
GET /api/v1/checks/00000000-0000-4000-8000-000000000036/findings?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Finding。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000037",
        "check_id": "00000000-0000-4000-8000-000000000036",
        "severity": "warning",
        "code": "REPETITIVE_TEXT",
        "message": "建议减少重复表述。",
        "resolution": null
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.97 POST /findings/{finding_id}/resolutions

权限：reviewer。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| action | accepted_warning/fixed! |
| note | string!1..2000 |
| replacement_check_id | uuid? |

blocker不能忽略；fixed必须新completed检查且确认问题消除。

请求示例：

```http
POST /api/v1/findings/00000000-0000-4000-8000-000000000037/resolutions
Authorization: Bearer <access-token>
Idempotency-Key: example-findings-resolve-001
Content-Type: application/json

{
  "action": "accepted_warning",
  "note": "该重复来自招标要求独立响应。"
}
```

成功响应：HTTP 200，data模型 Finding。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000037",
    "check_id": "00000000-0000-4000-8000-000000000036",
    "severity": "warning",
    "code": "REPETITIVE_TEXT",
    "message": "建议减少重复表述。",
    "resolution": {
      "action": "accepted_warning",
      "note": "该重复来自招标要求独立响应。",
      "replacement_check_id": null
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.98 GET /projects/{project_id}/content-snapshot

权限：owner/writer/reviewer及全部来源read。

参数：仅路径参数及通用头，无请求体。

hash含正文、来源、响应矩阵、审核及模板。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/content-snapshot
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 本节简单对象。

简单响应字段：snapshot_hash（string）、requirement_set_id（string）、outline_id（string）、chapter_version_ids（array）、project_lock_version（number）。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "outline_id": "00000000-0000-4000-8000-000000000027",
    "chapter_version_ids": [
      "00000000-0000-4000-8000-000000000030"
    ],
    "project_lock_version": 1
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.99 POST /projects/{project_id}/finalize

权限：owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| expected_snapshot_hash | hash! |
| check_id | uuid! |

当前所有章节批准、全文检查通过、blocker清零且warning处理；否则FINALIZATION_BLOCKED。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/finalize
Authorization: Bearer <access-token>
Idempotency-Key: example-projects-finalize-001
If-Match: "v1"
Content-Type: application/json

{
  "expected_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "check_id": "00000000-0000-4000-8000-000000000036"
}
```

成功响应：HTTP 201，data模型 FinalizedSnapshot。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000039",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "revoked_at": null,
    "chapter_version_ids": [
      "00000000-0000-4000-8000-000000000030"
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；特有 FINALIZATION_BLOCKED。

### 4.100 POST /projects/{project_id}/reopen

权限：owner。必需Idempotency-Key。必需If-Match（目标资源）。

| 参数 | 类型、必填及约束 |
|---|---|
| reason | string!1..1000 |

撤销定稿和产物，保留历史；后续内容修改使章节审核失效。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/reopen
Authorization: Bearer <access-token>
Idempotency-Key: example-projects-reopen-001
If-Match: "v1"
Content-Type: application/json

{
  "reason": "收到新补遗。"
}
```

成功响应：HTTP 200，data模型 Project。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000007",
    "name": "示例技术服务项目",
    "industry": "it",
    "status": "active",
    "owner_id": "00000000-0000-4000-8000-000000000003",
    "deadline": "2026-11-15T09:00:00+08:00",
    "active_requirement_set_id": "00000000-0000-4000-8000-000000000021",
    "active_outline_id": "00000000-0000-4000-8000-000000000027",
    "active_policy_id": "00000000-0000-4000-8000-000000000010",
    "finalized_snapshot_id": null,
    "lock_version": 2
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；版本冲突409、缺条件428；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.101 POST /projects/{project_id}/exports

权限：draft:owner/writer；final:owner。必需Idempotency-Key。

| 参数 | 类型、必填及约束 |
|---|---|
| mode | draft/final! |
| formats | docx/pdf[]!min1 |
| snapshot_id | uuid? |
| expected_snapshot_hash | hash! |

final必须有效snapshot_id；draft省略且水印。全部格式成功一起ready。

请求示例：

```http
POST /api/v1/projects/00000000-0000-4000-8000-000000000007/exports
Authorization: Bearer <access-token>
Idempotency-Key: example-exports-create-001
Content-Type: application/json

{
  "mode": "final",
  "formats": [
    "docx",
    "pdf"
  ],
  "snapshot_id": "00000000-0000-4000-8000-000000000039",
  "expected_snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

成功响应：HTTP 202，data模型 Accepted:export:exports。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "job": {
      "id": "00000000-0000-4000-8000-000000000042",
      "kind": "export",
      "status": "queued",
      "target_id": "00000000-0000-4000-8000-000000000049",
      "progress": 0,
      "attempt": 0,
      "lock_version": 1,
      "error": null
    },
    "resource": {
      "type": "exports",
      "id": "00000000-0000-4000-8000-000000000049"
    }
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；幂等冲突409；状态或资源前置条件不满足返回409，详细原因见code。

### 4.102 GET /projects/{project_id}/exports

权限：项目成员及来源read。

参数：仅路径参数及通用头、分页参数，无请求体。

revoked无下载入口。

请求示例：

```http
GET /api/v1/projects/00000000-0000-4000-8000-000000000007/exports?limit=20
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Export。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000049",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "mode": "final",
        "status": "ready",
        "snapshot_id": "00000000-0000-4000-8000-000000000039",
        "lock_version": 1,
        "files": [
          {
            "file_id": "00000000-0000-4000-8000-000000000903",
            "format": "docx",
            "download_url": "/api/v1/files/00000000-0000-4000-8000-000000000903/content"
          }
        ]
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.103 GET /exports/{export_id}

权限：项目成员及来源read。

参数：仅路径参数及通用头，无请求体。

下载走files/content再授权。

请求示例：

```http
GET /api/v1/exports/00000000-0000-4000-8000-000000000049
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Export。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": "00000000-0000-4000-8000-000000000049",
    "project_id": "00000000-0000-4000-8000-000000000007",
    "mode": "final",
    "status": "ready",
    "snapshot_id": "00000000-0000-4000-8000-000000000039",
    "lock_version": 1,
    "files": [
      {
        "file_id": "00000000-0000-4000-8000-000000000903",
        "format": "docx",
        "download_url": "/api/v1/files/00000000-0000-4000-8000-000000000903/content"
      }
    ]
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。

### 4.104 GET /audit-logs

权限：system_admin看脱敏系统记录；owner看本项目。

| 参数 | 类型、必填及约束 |
|---|---|
| Q project_id | uuid? |
| Q action | string? |
| Q actor_user_id | uuid? |
| Q from | datetime? |
| Q to | datetime? |

owner必须project_id；时间范围≤31天；不返回提示词、隐藏推理、密钥和原文。

请求示例：

```http
GET /api/v1/audit-logs?limit=20&project_id=00000000-0000-4000-8000-000000000007
Authorization: Bearer <access-token>
```

成功响应：HTTP 200，data模型 Page:Audit。

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "00000000-0000-4000-8000-000000000051",
        "action": "review.approved",
        "resource_type": "review",
        "resource_id": "00000000-0000-4000-8000-000000000034",
        "project_id": "00000000-0000-4000-8000-000000000007",
        "result": "succeeded",
        "request_id": "req-example-001"
      }
    ],
    "next_cursor": null
  },
  "request_id": "req-example-001"
}
```

错误：基础鉴权/可见性/字段错误按第6节；状态或资源前置条件不满足返回409，详细原因见code。


## 5. SSE运行事件协议

GET /runs/{run_id}/events返回text/event-stream，Cache-Control:no-store，关闭代理缓冲。客户端用支持Authorization的fetch流；禁止JWT放URL。首次先GET Run取得状态与last_event_seq，再用after=该序号订阅增量，避免获取状态与订阅之间丢事件；无游标时发送当前保留窗口。

持久事件字段id为run内单调递增seq，event为类型，data为{schema_version:1,run_id,seq,type,occurred_at,payload}。run.last_event_seq是持久高水位，清理事件不重置。事件和业务同事务，锁run分配序号。进度事件只含阶段、已完成数、资源ID、状态和脱敏错误，不流出正文或隐藏推理；正文通过版本接口授权读取。

```text
id: 21
event: review.requested
data: {"schema_version":1,"run_id":"00000000-0000-4000-8000-000000000041","seq":21,"type":"review.requested","occurred_at":"2026-10-16T10:00:00Z","payload":{"review_id":"00000000-0000-4000-8000-000000000034","chapter_version_id":"00000000-0000-4000-8000-000000000030"}}

: keepalive
```

事件名：run.created、run.status.changed、run.progress、chapter.version.created、review.requested、review.decided、run.completed、run.failed、run.cancelled。approved决定后进度以实际事务为准，客户端不能自行生成下一章。

Last-Event-ID优先，无该头才用after；同时给不同值422。服务发送seq>cursor；客户端按run_id+seq去重；允许重连重复，不允许顺序颠倒。每15秒心跳，无id不记账。令牌到期/撤权关闭连接，客户端刷新令牌重新授权；已发数据不能追回。

保留30天。cursor<events_retained_from-1返回410 EVENT_CURSOR_EXPIRED，包含retained_from、last_event_seq、snapshot_url；客户端重新GET状态后继续。cursor>last_event_seq返回409 EVENT_CURSOR_AHEAD。终态事件写入后发完保留增量再关闭；重连不触发任务。单条事件≤16KiB，输出字段白名单，不包含工具完整参数。

## 6. 错误码与恢复动作

| HTTP | code | 含义与客户端动作 |
|---|---|---|
| 401 | AUTH_INVALID / TOKEN_EXPIRED | 登录或刷新；不泄露账号存在性 |
| 403 | PERMISSION_DENIED | 当前可见资源上缺操作权限 |
| 403 | REVIEW_SELF_FORBIDDEN | 提交人与审核人相同，换审核人 |
| 403 | MODEL_POLICY_VIOLATION | 模型/来源边界不允许，不自动换云端 |
| 403 | ACCESS_DEPENDENCY_REVOKED | 某来源已撤权，停止展示派生内容 |
| 404 | RESOURCE_NOT_FOUND | 不存在或不可见 |
| 409 | VERSION_CONFLICT | 刷新ETag后重新合并，不覆盖人工内容 |
| 409 | IDEMPOTENCY_CONFLICT | 同键不同请求，使用新的业务操作键 |
| 409 | IDEMPOTENCY_IN_PROGRESS | 原请求进行中，遵守Retry-After |
| 409 | STATE_CONFLICT / IMMUTABLE_VERSION | 操作不适用于当前状态/冻结版本 |
| 409 | INPUT_NOT_READY | 来源未就绪、歧义或OCR需核实 |
| 409 | ACTIVE_TASK_EXISTS | 同项目已有活动run或归档前未清任务 |
| 409 | REVIEW_STALE | 审核快照过期，刷新版本重新提交 |
| 409 | FINALIZATION_BLOCKED | 返回脱敏阻断项ID，修复复检 |
| 409 | BUDGET_EXCEEDED | 需owner提高预算，不能无限重试 |
| 409 | UPLOAD_CONTENT_CONFLICT | 会话已上传不同内容，新建会话 |
| 409 | RUN_TERMINAL | 不允许对成功运行取消/重复推进 |
| 409 | EVENT_CURSOR_AHEAD | 游标超高水位，重新读取状态 |
| 410 | UPLOAD_EXPIRED | 重新建立上传会话 |
| 410 | EVENT_CURSOR_EXPIRED | 读取快照并以新高水位订阅 |
| 410 | CHECKPOINT_EXPIRED | 当前业务版本仍在，新建run |
| 413 | FILE_TOO_LARGE | 缩小文件 |
| 415 | UNSUPPORTED_MEDIA | 仅PDF/DOCX/XLSX，模板仅DOCX |
| 416 | INVALID_RANGE | 修正下载Range |
| 422 | VALIDATION_ERROR / FIELD_NOT_ALLOWED | 修复字段，按errors定位 |
| 422 | RETRIEVAL_SCOPE_TOO_LARGE | 缩小知识库查询范围，不去掉ACL |
| 428 | PRECONDITION_REQUIRED | 先读取目标ETag |
| 429 | RATE_LIMITED | 遵守Retry-After，不并发暴力重试 |
| 503 | MODEL_UNAVAILABLE / DEPENDENCY_UNAVAILABLE | 有界重试；任务状态可查 |
| 500 | INTERNAL_ERROR | 保留request_id交运维，不返回栈 |

每个接口都适用401/403/404/422等对应基础错误，带E/I标记的接口额外适用版本/幂等错误；业务特有错误在该接口说明中列出。异步执行失败通过Job/Run.error表达，不把提交时202事后改为500。worker被取消的未发布版本error.code=CANCELLED_BY_USER，是任务错误而非HTTP错误。

## 7. 调用顺序与验收

### 7.1 标准调用链

1. 登录→创建项目→配置模型policy→添加writer/reviewer→选择有权知识库。
2. uploads初始化→PUT二进制→complete→轮询ingest job→检查DocumentVersion.ready和OCR报告。
3. 创建requirement_set分析任务→查询条款/评分→必要的补录/校正→owner确认。
4. 创建outline任务→编辑候选节点→owner确认。
5. 创建run，GET状态后订阅SSE；current章节生成并提交review。
6. reviewer读取ChapterVersion及来源，携带ETag、version_hash和chapter_version_id批准/退回。
7. 通过后异步下一章；退回后writer手工PATCH并重新提交，或run.resume(reason=revise)。
8. 全部批准后GET content-snapshot→创建全文check→处理warning/修复blocker→owner finalize。
9. 以snapshot申请exports→等待ready→GET files/content下载DOCX/PDF。
10. 补遗重新分析生成新要求版本，确认后处理受影响章，旧定稿与产物失效。

每步写请求使用新的业务幂等键，同一步网络重试沿用原键。接口示例是单接口示意，不能跳过前置状态直接串行复制运行。

### 7.2 接口验收矩阵

| 场景 | 必须观察 |
|---|---|
| 未授权ID、伪造org、越权知识范围 | 404/403，未授权正文不进入模型 |
| 相同幂等键重复/不同body | 复用资源/409，无重复任务 |
| 过期If-Match、自审、旧版批准 | 409/403且业务不推进 |
| 修改已批章、补遗、来源撤销 | 状态失效、旧产物禁止下载、人工内容保留 |
| Worker崩溃、消息重复 | 状态最终收敛，版本和审核不重复 |
| run等待审核时resume | STATE_CONFLICT，不能绕过审核 |
| 令牌过期、SSE重连、事件保留期 | 正确关闭/补发/410及快照恢复 |
| 取消并发模型回调 | 费用可记，正文不能继续提交 |
| 大/坏/加密/宏文件、OCR低质量 | 明确失败或waiting_input，不空内容成功 |
| final导出未定稿、模板缺字、版本变化 | 阻断或revoked，不静默生成正式文件 |

未来实现时由同一Pydantic模型生成OpenAPI3.1，文档示例作为契约夹具；校验请求/响应schema、状态码、ETag、幂等和SSE。当前只做设计一致性检查，没有调用真实API、数据库或模型。

