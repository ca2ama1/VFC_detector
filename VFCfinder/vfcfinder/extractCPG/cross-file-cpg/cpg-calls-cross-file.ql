/**
 * @name Cross-File Function Calls
 * @description Finds function calls that cross file boundaries
 * @kind traversal
 * @tags efficiency
 * @id cpp/cross-file-function-calls
 */

import cpp
import traversal::Traversable

// A call that crosses file boundaries
class CrossFileCall extends Call {
  CrossFileCall() {
    exists(Function callee, File callerFile, File calleeFile |
      this.getCalled() = callee.getADeclaration() and
      callerFile = this.getFile() and
      calleeFile = callee.getDefinition().getContainer().getFile() and
      callerFile != calleeFile
    )
  }
}

from CrossFileCall call
select call, "This function call crosses file boundaries from " + call.getFile().getName() + " to " + call.getCalled().getName()
