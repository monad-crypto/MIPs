object "CreateBigFactory" {
    code {
        datacopy(0, dataoffset("runtime"), datasize("runtime"))
        setimmutable(0, "self", address())
        return(0, datasize("runtime"))
    }
    object "runtime" {
        code {
            // deploy(bytes32 salt, bytes initcode, uint256 value, uint256 maxDepositValue)
            if iszero(eq(shr(224, calldataload(0)), 0xdc61e1cd)) { revert(0, 0) }

            let salt            := calldataload(4)
            let value           := calldataload(68)
            let maxDepositValue := calldataload(100)
            let len             := calldataload(132)

            // initcode size limit (MIP-21 MAX_DEPLOY_INITCODE_SIZE); also prevents overflow below
            if gt(len, 368640) { revert(0, 0) }

            // strict ABI decoding: canonical offset, exact padded length
            if iszero(eq(calldataload(36), 0x80)) { revert(0, 0) }
            if iszero(eq(calldatasize(), add(164, and(add(len, 31), not(31))))) { revert(0, 0) }

            let direct := eq(address(), loadimmutable("self"))

            if direct {
                // bind salt to caller
                mstore(0, caller())
                mstore(32, salt)
                salt := keccak256(0, 64)
                let required := add(value, maxDepositValue)
                if lt(required, value) { revert(0, 0) }      // overflow
                if lt(callvalue(), required) { revert(0, 0) }
            }

            calldatacopy(0, 164, len)

            // CREATEBIG (MIP-21): EXTENSION (0xae), selector 0x02
            let deployed := verbatim_5i_1o(hex"ae02", value, 0, len, salt, maxDepositValue)
            if iszero(deployed) {
                returndatacopy(0, 0, returndatasize())
                revert(0, returndatasize())
            }

            // deposit = (CODE_DEPOSIT_COST - PARTIAL_CODE_DEPOSIT_COST) * |R| * basefee
            let deposit := mul(mul(extcodesize(deployed), 120), basefee())

            if direct {
                let refund := sub(callvalue(), add(value, deposit))
                if refund {
                    if iszero(call(gas(), caller(), refund, 0, 0, 0, 0)) { revert(0, 0) }
                }
            }

            mstore(0, deployed)
            mstore(32, deposit)
            return(0, 64)
        }
    }
}
