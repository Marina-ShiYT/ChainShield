// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AccessControlSample {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function changeOwner(address newOwner) public {
        owner = newOwner;
    }
}
