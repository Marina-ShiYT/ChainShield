// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract UncheckedCallSample {
    function unsafeCall(address target) public {
        target.call("");
    }
}
