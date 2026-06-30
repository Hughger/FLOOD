`ifndef CONFIG_V
`define CONFIG_V

//////////////////////////////////////////////////////////////////////////////
// 自动生成的配置头文件 - 与 Config.scala 保持同步
//////////////////////////////////////////////////////////////////////////////

// ========== 基本架构参数 ==========
`define ROW_SIZE 4
`define COL_SIZE 4
`define TILE_SIZE 4
`define DATA_WIDTH 8
`define OUTPUT_WIDTH 19               // 2*DATA_WIDTH + log2(ROW_SIZE)
`define FEATURE_MAP_BAND_WIDTH 32     // COL_SIZE * DATA_WIDTH
`define WEIGHT_BAND_WIDTH 32          // 同 FEATURE_MAP_BAND_WIDTH

// ========== 配置总线参数 ==========
`define CONFIG_DATA_WIDTH 32
`define CONFIG_ADDR_WIDTH 32

// ========== FSM/OutRouter 配置位宽 ==========
`define KERNEL_BLOCK_K_WIDTH 4        // log2Ceil(16)
`define GROUP_SIZE_WIDTH 4            // log2Ceil(16)
`define GROUP_NUM_WIDTH 4             // log2Ceil(16)
`define KERNEL_BLOCK_COUT_WIDTH 5     // log2Ceil(32)
`define CIN_IDX_WIDTH 9               // log2Ceil(1024/ROW_SIZE + 1)
`define RESOLUTION_COL_IDX_WIDTH 8    // log2Ceil(768/COL_SIZE + 1)
`define WORK_MODE_WIDTH 3             // log2Ceil(5)

// ========== 配置寄存器地址 ==========
`define TILE_CONF_ID_START 0
`define TILE_CONF_ID_END 3            // TILE_SIZE-1
`define NOC_CONF_ID_START 4           // TILE_SIZE
`define NOC_CONF_ID_END 6             // 2*TILE_SIZE-2
`define FSM_ROUTER_CONF_ID_START 7    // 2*TILE_SIZE-1
`define FSM_ROUTER_CONF_ID_END 8      // 2*TILE_SIZE
`define BN_CONF_ID_START 9            // 2*TILE_SIZE+1
`define BN_CONF_ID_END 12             // 2*TILE_SIZE+COL_SIZE
`define GLOBAL_CONF_ID 14             // 2*TILE_SIZE+COL_SIZE+2
`define RUN_PROCESS_ID 12             // 3*TILE_SIZE
`define INTERRUPT_FRESH_ID 13         // 3*TILE_SIZE+1

// ========== SRAM 参数 ==========
`define WEIGHT_SRAM_LENGTH 1024
`define OUTPUT_SRAM_LENGTH 1024
`define JOINT_SRAM_LENGTH 1024
`define OUTPUT_BUFFER_TMP_WIDTH 16
`define OUTPUT_BUFFER_DATA_WIDTH 16

// ========== 其他参数 ==========
`define MAX_KERNEL_BLOCK_K 16
`define MAX_GROUP_SIZE 16
`define MAX_GROUP_NUM 16
`define MAX_KERNEL_BLOCK_COUT 32
`define MAX_KERNEL_BLOCK_CIN 1024
`define MAX_RESOLUTION_COL 768
`define MAX_WORK_MODE 5

`endif // CONFIG_V