import { ComponentMeta, ComponentRegistry } from "@inductiveautomation/perspective-client";
import { RagChatMeta } from "./components/RagChat";

export { RagChatMeta };

import "../scss/main";

const components: Array<ComponentMeta> = [
    new RagChatMeta()
];

components.forEach((c: ComponentMeta) => ComponentRegistry.register(c));
