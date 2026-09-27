    <g transform="translate($x_end,0)">
      <animateTransform attributeName="transform" type="translate" values="$x_start 0; $x_end 0; $x_end 0" keyTimes="0; $move_end; 1" calcMode="linear" dur="${dur}s" begin="${begin}s" repeatCount="indefinite"/>
      <rect x="$post1_x" y="$post_y" width="$post_w" height="$post_h" fill="$post_color"/>
      <rect x="$post2_x" y="$post_y" width="$post_w" height="$post_h" fill="$post_color"/>
      <rect x="$board_x" y="$board_y" width="$board_w" height="$board_h" rx="3" fill="$board_color" stroke="$border_color" stroke-width="2"/>
$lines
    </g>
