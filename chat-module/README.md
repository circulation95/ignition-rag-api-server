# Perspective Component Module Example

This is an example module which adds some custom components to the Perspective module.  There are 3 different components
in this example, each exercising different aspects of the Perspective component API, as well as demonstrating
a few different ways of dealing with data and configuration of the components in the gateway designer.

### Summary of Components

#### 1. Image

Most basic component, provides a reference for the 'bare minimum' required to create a component and register it in the
appropriate registries such that it's available on the palette in the designer and in the client at runtime.

#### 2. TagCounter

Demonstrates a component that provides a custom Java/Swing based configuration UI when the component is selected in the
designer.  In addition, utilizes the gateway's `RouteGroup` api to create a web endpoint from which the component can
fetch data outside of the Perspective property tree system.

#### 3. Messenger Component

Somewhat silly example demonstrates the use of a Mobx based state class (component model/store) to contain state outside
of the PropertyTree system, as well as demonstrates the use of the Store/Model Message Delegate API, which is a way to
send data between the gateway and browser via perspective's 'real time' websocket communication channel.

These examples are only a few of the countless ways a savvy developer can build a module targeting Perspective.
Ultimately it's up to implementors to choose the tools they prefer.


## Quick Tool Overview

This project uses a number of build tools in order to complete the various parts of its assembly.  It's importatnt to note that these tools are just some example options.  You may use any tool you want (or no tool at all).  These examples use:

* [Gradle](https://gradle.org/) - the primary build tool. Most tasks executed in a typical workflow are gradle tasks.
* [lerna.js](https://lernajs.io/) - is a javascript build-orchestration tool.  It allows us to have independent 'modules'
 and 'packages' in the same git/hg repository without having to do a lot of complicated symlinking/publishing to pull in changes from one project to another.  It's mostly useful from the commandline, outside of gradle.
* [yarn](https://yarnpkg.com/) - is a javascript dependency (package) manager that provides a number of improvements
over npm, though it shares much of the same commands and api.  Much like Ivy or Maven, yarn is used to resolve and download dependencies hosted on remotely hosted repositories.  Inductive Automation publishes our own dependencies through the
 same nexus repository system we use for other sdk artifacts.  To correctly resolve the Inductive Automation node packages,
  an `.npmrc` file needs to be added to the front end projects to tell yarn/npm where to find packages in the `@inductiveautomation` namespace.  You will find examples of these in the `web/` directory.
* [Typescript](https://www.typescriptlang.org/) - the language used to write the front end parts.  Typescript is not required, but is strongly recommended.  Typescript can be thought of as modern javascript with types added (though this is a simplification). The addition of types to JS results in a far better developer experience through much better tooling
  support.  This can improve maintainability, refactoring, code navigation, bug discovery, etc.  Typescript has its own compiler which emits javascript.  This compiler is frequently paired with other build tools in a way that it emits the javascript, but
  other tools handle the actual bundling of assets, css, and other supporting dependencies.  Think of typescript as the
  java compiler without jars or resources.  It just takes typescript files in, and emits the javascript files.
* [Webpack](https://webpack.js.org/) - the 'bundler' that we use to take the javascript emitted by the typescript compiler and turn it into an actual package that includes necessary assets, dependencies, generates sourcemaps, etc.


More documentation incoming, and the web/README.md contains a lot of information about the typescript build process.

## Getting Started

This is a quick-start set of requirements/commands to get this project built.

Strictly speaking, this module should be buildable without downloading or installing any additional tools.  If
build commands are executed through the [Gradle Wrapper](https://docs.gradle.org/current/userguide/gradle_wrapper.html),
it will handle downloading the appropriate versions of all tools, and then use those tools to execute the build.


> Note: the module related task are defined by the module plugin.  Check the documentation at the [Ignition Module Tool](https://github.com/inductiveautomation/ignition-module-tools) repository for more information about the tasks and configuration options.

To run the build, clone this repo and open a command line in the `perspective-component` directory, and run the `build` gradle task:

```
// on Windows
gradlew build

// on linux/osx
./gradlew build
```

If you would like to be able to execute parts of the build without depending on gradle, you'll need familiarity with
the javascript and typescript ecosystem, including NodeJs, NPM/Yarn, Typescript, Webpack, Babel, etc.

While not a comprehensive instruction set, the process of setting up these tools would look something like the following:

1. Install node and npm, which can be used to further install yarn, typescript, webpack, etc.  MacOs and Linux can
install via package managers, or they and Windows can be installed via the downloads at the
[NodeJS Website](https://nodejs.org/).   We recommend sticking with the LTS versions (actual versions used by the build)
can be seen in the `./web/build.gradle` file, within the `node` configuration block.

2. With npm installed, install the global dev-dependency tools.  While it's possible to make gradle handle all these,
it's useful to have them installed locally to speed build times and run local checks and commands without gradle.  In
general, you want these to be the same (or very close) version as those defined in your package.json files.
    1. `npm install -g typescript`
    2. `npm install -g webpack@3.10.1`   // or whatever version you want
    3. `npm install -g tslint`
    4. `npm install -g lerna`
    5. `npm install -g yarn`

3. Gradle - gradle does not need to be installed if commands are executed through the gradle wrapper (see
[Gradle Wrapper Docs](https://docs.gradle.org/current/userguide/gradle_wrapper.html) for details).


Quick Note:  This example is built using a custom gradle plugin developed by IA in order to build Ignition modules.
This plugin was originally intended for  internal use and, as a result, it makes some assumptions about project
structure and dependencies.  If you are familiar with Maven and wish to use it to build perspective modules, you may
do so, though we do not plan integrating nor supporting Perspective module development with the `ignition-maven-plugin`.

### Project structure & Layout

This section provides a high-level overview of the different parts of this project.  For additional details about
the `web` subproject, see the readme there.

This example module has a fairly traditional Ignition Module project layout with one key difference.  Like most cross-scope projects, this one has a `common` subproject which is  shared between gateway and designer scopes.  What it does NOT
have is a `client` scope.  Instead we have a `web` subproject which contains the source code, assets, and build
configuration used to build the html/js/css used in the module.

Within the `web` directory is a _lerna workspace_, which is simply a javascript corollary to a 'maven multi-module
 project',  or a 'multi-project gradle build'.  Meaning, there are more than one 'build' configured.  We have stuck
 with the lerna default of using `packages` directory that has our two builds - one targeting a perspective client
 at runtime in a browser, and a second targeting perspective in the designer.  As in Vision, the perspective designer
 scoped assets frequently extend the perspective client scoped assets (again, remembering that this is client in the
  context of the web, meaning executing in a web browser.  Nothing to do with _vision clients_).  Ultimately the output
  of both web/ packages ends up in our `gateway` scoped java project as resources, as the gateway is where they get
  served from.  That they are named `client` or `designer` is unimportant.  They could be `browser` and `designer` or
  whatever you choose.  The important part is making sure the files are appropriately registered in the appropriate
  registries.



```


  ├── build.gradle.kts                     // root build configuration, like a root pom.xml file
  ├── common
  │   ├── build.gradle.kts                     // configuration for common scoped build
  │   └── src
  │       └── main/java                    // where source files live
  ├── designer
  │   ├── build.gradle.kts
  │   └── src
  │       └── main/java
  ├── gateway
  │   ├── build.gradle.kts
  │   └── src
  │       └── main/java
  ├── gradle                              // gradle wrapper assets to allow wrapper functionality,should be commited
  │   └── wrapper
  │       ├── gradle-wrapper.jar
  │       └── gradle-wrapper.properties
  ├── gradlew                             // gradle build script for linux/osx
  ├── gradlew.bat                         // gradle build script for windows
  ├── settings.gradle.kts                 // Gradle project structure/global configuration.
  └── web                                 // parent directory for the web assets we build
      ├── README.md
      ├── build.gradle.kts
      ├── lerna.json                      // lerna configuration file
      │
      ├── package.json
      ├── packages
      │   ├── client
      │   │    ├── package.json
      │   │    ├── webpack.config.json     // webpack build configuration
      │   │    └── typescript/             // typescript source files
      │   │
      │   └── designer
      │        ├── package.json
      │        ├── webpack.config.json     // webpack build configuration
      │        └── typescript/             // typescript source files
      └── yarn.lock                        // lock file describes the dependencies/versions of front-end resources

```

### Building

Building this module through the gradle wrapper is easy!

 In a bash (or any similar posix) terminal execute `./gradlew build` (linux/osx).  If on windows, run
`gradle.bat build`.  This will result in the appropriate gradle binaries being downloaded (match the version
 and info provided by our `wrapper` task and committed `gradle/` directory).  This will compile and assemble all jars,
run all tests/checks, and ultimately create the signed modl file. Note that to sign your module, you'll need appropriate
 signing certificates, and a `gradle.properties` file that points to those certificates, following the configuration
 described on plugin readme in the [Tools Repository](https://www.github.com/inductiveautomation/ignition-module-tools).


 ### Configuring/Customizing

How to configure and customize the build is outside the scope of this example.  We encourage you to read the docs of
the various tools used and linked above to determine the appropriate build configurations for your project.

### SDK Tips

Perspective is a fairly complex system that is seeing regular changes/additions.  While we consider the APIs 'mostly stable', there will likely be additions and/or breaking changes as it matures.  As a result, we encourage testing modules against each version of Ignition/Perspective you intend to support.

#### Standards

As of the 8.1.4 release, a `ref` is passed down to the component via `emit` (emit props).  This is required to
provide back a reference to the root element of each component, which is used internally by the Perspective module.
For this reason, the root element of any authored components cannot contain a `ref` property.  Doing so will
override the emitted ref and will not allow your component to properly display any changes to the state of its
qualities and may cause the component to throw an error.  The ref can still be accessed from the component's store,
if needed.  In addition, it is highly recommended that the root element does not change throughout the lifecycle
of the component.  For more information and an example usage, see the `MessengerComponent` from the example
components.

---

## Chat Module for RAG API Server

This module provides a custom Perspective component that integrates with the Ignition SCADA AI Agent RAG API Server, enabling real-time AI-powered chat functionality within Ignition Perspective views.

### Features

- **AI Chat Interface**: Interactive chat component with message history
- **RAG Integration**: Connects to the multi-agent RAG API server
- **Real-time Communication**: WebSocket-based updates for instant responses
- **Configurable Endpoint**: Easy configuration of API server URL
- **Session Management**: Thread-based conversation tracking

### Building the Module

#### Prerequisites

- Java JDK 11 or higher
- Gradle (or use the included Gradle Wrapper)
- Node.js 14+ and npm/yarn (for web assets)

#### Build Steps

1. **Navigate to the chat-module directory**:
   ```bash
   cd chat-module
   ```

2. **Build using Gradle Wrapper** (recommended):
   ```bash
   # On Windows
   gradlew.bat build

   # On Linux/macOS
   ./gradlew build
   ```

3. **Locate the built module**:
   The compiled `.modl` file will be in:
   ```
   build/
   ```

4. **Sign the module** (optional, for production):
   Configure signing in `gradle.properties`:
   ```properties
   ignition.signing.keystoreFile=/path/to/keystore.jks
   ignition.signing.keystorePassword=yourPassword
   ignition.signing.certAlias=yourAlias
   ignition.signing.certPassword=certPassword
   ```

### Installing the Module

1. Open Ignition Gateway webpage (http://localhost:8088 by default)
2. Navigate to **Config → System → Modules**
3. Click **Install or Upgrade a Module**
4. Select the built `.modl` file
5. Restart the Gateway when prompted

### Configuring the Chat Component

#### 1. Add Component to Perspective View

In the Perspective Designer:
1. Open or create a Perspective view
2. Drag the **Chat** component from the component palette
3. The component will appear in your view

#### 2. Configure endpointUrl Property

Set the API endpoint URL in the component properties:

**Option A: Direct Property Binding**
```json
{
  "endpointUrl": "http://localhost:8000/api/v1/ask"
}
```

**Option B: Using View Parameters**
1. Create a view parameter `apiEndpoint`:
   ```json
   {
     "apiEndpoint": "http://localhost:8000/api/v1/ask"
   }
   ```

2. Bind the component's `endpointUrl` property:
   ```
   {view.params.apiEndpoint}
   ```

**Option C: Using Session Properties** (recommended for production)
1. Set a session custom property `ragApiUrl`:
   ```
   http://localhost:8000/api/v1/ask
   ```

2. Bind the component's `endpointUrl` property:
   ```
   {session.custom.ragApiUrl}
   ```

#### 3. Additional Component Properties

Configure other important properties:

```json
{
  "endpointUrl": "http://localhost:8000/api/v1/ask",
  "approvalEndpoint": "http://localhost:8000/api/v1/approve",
  "threadId": "user_session_{session.props.auth.user.userName}",
  "showTimestamps": true,
  "maxMessages": 100,
  "placeholder": "Ask about your SCADA system..."
}
```

### Using the Chat API

The chat component automatically handles API communication. Here's how it works:

#### Sending Messages

When a user types a message and hits send, the component makes a POST request:

**Request:**
```http
POST http://localhost:8000/api/v1/ask
Content-Type: application/json

{
  "question": "현재 Tank1 온도는?",
  "thread_id": "user_session_admin"
}
```

**Response (Simple Query):**
```json
{
  "intent": "chat",
  "answer": "**Tank1 온도:** 75°C\n\n현재 정상 범위 내에 있습니다."
}
```

**Response (Approval Required):**
```json
{
  "intent": "chat",
  "status": "pending_approval",
  "answer": "⚠️ 쓰기 작업은 승인이 필요합니다...",
  "thread_id": "user_session_admin",
  "pending_action": {
    "action_id": "abc-123-def-456",
    "tag_path": "[default]FAN/FAN1",
    "value": 0,
    "risk_level": "high",
    "message": "Write operation requires approval..."
  }
}
```

#### Approving Actions

When a write operation requires approval, the component displays an approval dialog. Upon approval:

**Request:**
```http
POST http://localhost:8000/api/v1/approve
Content-Type: application/json

{
  "thread_id": "user_session_admin",
  "action_id": "abc-123-def-456",
  "approved": true,
  "operator": "admin",
  "notes": "Approved for maintenance"
}
```

**Response:**
```json
{
  "status": "executed",
  "action_id": "abc-123-def-456",
  "message": "쓰기 작업이 성공적으로 실행되었습니다",
  "result": {
    "tag_path": "[default]FAN/FAN1",
    "value": 0,
    "executed_at": "2026-02-15T14:35:00"
  }
}
```

### Example Query Scenarios

#### 1. Real-time Tag Reading
```
User: "Tank1 온도는?"
Response: 현재 Tank1/Temperature: 75°C
```

#### 2. Historical Data Analysis
```
User: "FAN1 어제 히스토리 보여줘"
Response: [Chart with historical data and statistics]
```

#### 3. Alarm Investigation
```
User: "현재 알람을 분석해줘"
Response: [Multi-agent analysis with alarm details, correlations, and recommendations]
```

#### 4. Control Operations (with approval)
```
User: "FAN1을 꺼줘"
Response: [Approval dialog]
→ User approves
→ Execution confirmation
```

### Troubleshooting

#### Component doesn't appear in palette
- Verify the module is installed and activated
- Restart the Ignition Gateway
- Clear the designer cache

#### API connection errors
- Check the `endpointUrl` property is correctly set
- Verify the RAG API server is running (`http://localhost:8000/api/v1/health`)
- Check network connectivity and firewall rules
- Review Gateway logs for detailed error messages

#### Messages not sending
- Open browser developer console for errors
- Verify the endpoint URL format is correct
- Check that the API server is accessible from the Gateway
- Ensure CORS is properly configured if using different domains

### Development Notes

For developers modifying the chat component:

1. **Web assets** are in `web/packages/client/typescript/components/`
2. **Component registration** is in `gateway/src/main/java/.../ChatComponentRegistry.java`
3. **Backend logic** (if any) is in the gateway scope
4. **Rebuild web assets**: `./gradlew web:build`
5. **Hot reload**: Use `./gradlew deployModl` with a local gateway configured

### API Server Setup

Ensure the RAG API Server is running before using the chat component:

```bash
# In the rag-api-server directory
cd ../
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify the server is running:
```bash
curl http://localhost:8000/api/v1/health
```

For more information about the RAG API Server, see the [main README](../README.md).
