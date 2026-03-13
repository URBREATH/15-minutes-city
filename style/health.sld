<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:se="http://www.opengis.net/se" version="1.1.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <se:Name>urbreath_aarhus_walkability_health</se:Name>
    <UserStyle>
      <se:Name>urbreath_aarhus_walkability_health</se:Name>
      <se:FeatureTypeStyle>
        <se:Rule>
          <se:Name>less than 5 min</se:Name>
          <se:Description>
            <se:Title>less than 5 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>0</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>5</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#009200</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>5 - 10 min</se:Name>
          <se:Description>
            <se:Title>5 - 10 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>5</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>10</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#32d700</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>10 - 15 min</se:Name>
          <se:Description>
            <se:Title>10 - 15 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>10</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>15</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#aedd00</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>15 - 20 min</se:Name>
          <se:Description>
            <se:Title>15 - 20 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>15</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>20</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#e4d700</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>20 - 25 min</se:Name>
          <se:Description>
            <se:Title>20 - 25 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>20</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>25</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#ff9933</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>25 - 30 min</se:Name>
          <se:Description>
            <se:Title>25 - 30 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>25</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>30</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#f40000</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>30 - 60 min</se:Name>
          <se:Description>
            <se:Title>30 - 60 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:Literal>30</ogc:Literal>
                <ogc:PropertyName>health</ogc:PropertyName>
              </ogc:PropertyIsLessThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>health</ogc:PropertyName>
                <ogc:Literal>60</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#8a0000</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>> 60 min</se:Name>
          <se:Description>
            <se:Title>> 60 min</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:PropertyIsNull>
              <ogc:PropertyName>health</ogc:PropertyName>
            </ogc:PropertyIsNull>
          </ogc:Filter>
          <se:PolygonSymbolizer>
            <se:Fill>
              <se:SvgParameter name="fill">#696762</se:SvgParameter>
              <se:SvgParameter name="fill-opacity">0.7</se:SvgParameter>
            </se:Fill>
            <se:Stroke>
              <se:SvgParameter name="stroke">#a9a9a9</se:SvgParameter>
              <se:SvgParameter name="stroke-opacity">0</se:SvgParameter>
              <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
              <se:SvgParameter name="stroke-linejoin">bevel</se:SvgParameter>
            </se:Stroke>
          </se:PolygonSymbolizer>
        </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
