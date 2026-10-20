# Network Library

The `Network` library provides a high-level interface for RemoteEvents and RemoteFunctions in Roblox.
It automatically manages the creation, replication, and invocation of remotes, so you don’t have to manually create folders, assign remotes, or handle client/server differences.
Remote names are defined in one place, which reduces typo-prone string usage and improves editor completion.

---

## 🧩 Features

* Automatic creation of RemoteEvent and RemoteFunction folders and instances.
* Named remote constants, reducing typo-prone string usage and providing auto-complete.
* Automatic client/server distinctions when connecting events or binding functions.
* Client/server invocation helpers that return `pcall` success and result values.
* Lightweight and modular, fully compatible with Rojo and VS Code workflows.

---

## 🧩 Dependencies

The library relies on a few simple internal modules:

* `RemoteEventName` — Enum of all RemoteEvent names for use with `Network`.
* `RemoteFunctionName` — Enum of all RemoteFunction names for use with `Network`.
* `RemoteFolderName` — Constants for the RemoteEvents and RemoteFunctions folder names.
* `createRemotesFolders` — Creates the folders for remotes and populates them with instances.
* `waitForAllRemotesAsync` — Waits for all remotes to replicate on the client before usage.
* `getInstance` — Safely retrieves a nested Instance or an instance created at runtime (like our remotes), erroring if the path is invalid.

All dependencies are included within the Network library folder, so no additional installation is required.

---

## 🧩 Getting Started

### Server Setup

```lua
local Network = require(ReplicatedStorage.Network)

-- Initialize remotes on the server
Network.startServer()
```

### Client Setup

```lua
local Network = require(ReplicatedStorage.Network)

-- Wait for server to replicate all remotes
Network.startClientAsync()
```

> ⚠️ Both `startServer()` and `startClientAsync()` must be called before any other Network functions.

> 💡 If using the [Modular Framework](../ModularFramework/), make sure to call these start functions from the single server and local scripts **before** calling the `ModuleLoader` function.

---

## 🧩 Using Network

### Connecting RemoteEvents

```lua
Network.connectEvent(Network.RemoteEvents.ExampleRemote1, function(player, message)
    print(player.Name, message)
end)
```

Automatically handles `OnServerEvent` vs `OnClientEvent`.

---

### Binding RemoteFunctions

```lua
Network.bindFunction(Network.RemoteFunctions.ExampleRemoteFunction, function(player, x, y)
    return x + y
end)
```

Automatically handles `OnServerInvoke` vs `OnClientInvoke`.

---

### Firing Events

```lua
-- From client to server
Network.fireServer(Network.RemoteEvents.ExampleRemote1, "Hello Server!")

-- From server to one client
Network.fireClient(Network.RemoteEvents.ExampleRemote1, player, "Hello Player!")

-- From server to all clients
Network.fireAllClients(Network.RemoteEvents.ExampleRemote1, "Hello Everyone!")

-- From server to all clients except one
Network.fireAllClientsExcept(Network.RemoteEvents.ExampleRemote1, excludedPlayer, "Hello Everyone Else!")
```

---

### Invoking Functions

```lua
-- Client calls server function
local success, result = Network.invokeServerAsync(Network.RemoteFunctions.ExampleRemoteFunction, 2, 3)

-- Server calls client function
local success, result = Network.invokeClientAsync(Network.RemoteFunctions.ExampleRemoteFunction, player, 2, 3)
```

All invocations are wrapped in `pcall`, so errors are returned as `success = false`. A `RemoteFunction` can still yield while waiting for its handler, so use a `RemoteEvent` plus your own timeout for calls that must not block.
