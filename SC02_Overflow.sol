// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract OverflowSample {
    uint8 public counter = 255;

    function increment() public {
        counter += 1;
    }
}
