// 阻止Windows发布版本显示额外控制台窗口
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    deepresearchpro_temp_lib::run()
}
