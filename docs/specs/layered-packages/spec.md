# Layered packages

## Problem

The bots package is now split into four layers. The other twelve feature packages are still flat. A reader has to open each file to learn whether it holds data, storage, logic that acts, or routes. Only the session package has a check that its data never reaches into storage. No other package has that check.

## What changes for you

Nothing a person sees in the app changes. No route, page, stored file or tool changes.

The code reads differently after the change.

1. A developer opens any feature package and sees the same four folders: domain, repository, service and router.
2. The domain folder holds the data shapes and the rules that only compute.
3. The repository folder holds the storage: a port, and the backends behind it.
4. The service folder holds the code that acts: services, schedulers, workers, connections and the tools a model calls.
5. The router folder holds the routes and their request and response bodies.
6. A package with no routes or no storage leaves out that folder.
7. A test fails if a domain module imports its own package's other layers, or does input or output.

## Decisions

- Every feature package gets the layers, not only the packages with a service per page. The person chose this at the scope question. Cell mode's naming rule prefers folders named for a subject over layer words. The person's choice wins here.
- A folder that is already a subject of its own keeps its shape. These are the three chat platforms, the client tools and each native tool. To decide at approval.
- The main file in each layer takes the package's subject and the layer as its name, as in the bots package. Other files keep their names. To decide at approval.
- A storage port takes its subject as its name. A backend behind it adds the backend's name in front. To decide at approval.
- A module goes to the domain folder only when it does no input or output and imports no storage. Anything else that acts goes to the service folder. To decide at approval.
- Each package's public names stay the same. A caller that imports the package itself does not change. Only imports of a module inside a package are rewritten.

## Out of scope

- The model seam, the turn loop, the sandbox, the config and the composition root. They are not feature packages.
- Any change to what a function does, returns, saves or raises.
- Renaming a class or a function. Only modules and folders move.

## How we will know it works

- The full backend suite passes before and after each ticket. Today it is 2041 tests at 98% coverage (measured on the bots branch).
- The lint passes, including the 300-line cap.
- The app's server module imports without error.
- The new layering test passes for every layered package, and fails when we make a domain module import its own service.
- The session package's existing checks still pass, rewritten for its new folders.
