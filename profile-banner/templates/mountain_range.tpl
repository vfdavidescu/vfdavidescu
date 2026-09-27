    <g transform="translate($x_end,0)">
      <animateTransform attributeName="transform" type="translate" values="$x_start 0; $x_end 0; $x_end 0" keyTimes="0; $move_end; 1" calcMode="linear" dur="${dur}s" begin="${begin}s" repeatCount="indefinite"/>
      <polygon points="$points" fill="$color"/>
    </g>
