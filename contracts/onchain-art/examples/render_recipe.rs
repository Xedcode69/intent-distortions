//! Offline independent decoder of the exact bytes served by the onchain views.
#[path = "../src/renderer.rs"]
mod renderer;
fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 4, "render_recipe RECIPE TITLE OUTPUT_DIRECTORY");
    let bytes = std::fs::read(&args[1]).unwrap();
    let scene = renderer::decode(&bytes).expect("Invalid IDART1 recipe");
    let directory = std::path::Path::new(&args[3]);
    std::fs::create_dir_all(directory).unwrap();
    for (name, animated) in [("static.svg", false), ("animated.svg", true)] {
        let svg = renderer::svg(&scene, &args[2], animated).unwrap();
        std::fs::write(directory.join(name), svg).unwrap();
    }
    println!(
        "Rendered {} frozen shapes; {} recipe bytes",
        scene.shapes.len(),
        bytes.len()
    );
}
