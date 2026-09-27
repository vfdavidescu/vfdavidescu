  <line x1="0" y1="$lane_y" x2="$width" y2="$lane_y" stroke="$lane_color" stroke-width="$lane_width" stroke-dasharray="$lane_dash">
    <animate attributeName="stroke-dashoffset" from="$dash_from" to="$dash_to" dur="${lane_dur}s" repeatCount="indefinite"/>
  </line>
