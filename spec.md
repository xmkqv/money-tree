````md:spec
<rules layer="layer-system">
```sql:types
type data_type = (type_name)
type loader_type = (type_name)
type transformer_type = (type_name)
type model_type = (type_name)
type decider_type = (type_name)
type trader_type = (type_name)
type data_output = (value)
type loader_output = (value)
type transformer_output = (value)
type model_output = (value)
type decider_output = (value)
type trader_output = (value)
type data_adapter = (data_type, trader_output, data_output)
type loader_adapter = (loader_type, data_output, loader_output)
type transformer_adapter = (transformer_type, loader_output, transformer_output)
type model_adapter = (model_type, transformer_output, model_output)
type decider_adapter = (decider_type, model_output, decider_output)
type trader_adapter = (trader_type, decider_output, trader_output)
```
```md:api
<api>
adaptData(data_type, trader_output): data_output
adaptLoader(loader_type, data_output): loader_output
adaptTransformer(transformer_type, loader_output): transformer_output
adaptModel(model_type, transformer_output): model_output
adaptDecider(decider_type, model_output): decider_output
adaptTrader(trader_type, decider_output): trader_output
</api>
```
<rules layer="interface-shape">
    every layer declares exactly one generic adapter
    every generic adapter is its layer interface
    every generic adapter accepts one type discriminator
    every generic adapter declares one payload input
    every generic adapter declares one output
    system composition depends only on generic adapters
</rules>
<rules layer="module-shape">
    every implementation type has a valid name
    every type module owns exactly one implementation type
    every implementation type is implemented in exactly one type module
    every type module belongs to exactly one layer
    every type module is a direct child of one layer root
    every layer root owns exactly one package initializer
</rules>
<rules layer="module-selection">
    every implementation type has exactly one type discriminator
    every type discriminator names exactly one implementation type
    every layer resolves type discriminators within its direct child modules
    an unresolved type discriminator is invalid
    a discriminator change selects another implementation within one layer
    a discriminator change preserves the generic adapter
</rules>
<rules layer="scope">
    the scope includes the data layer
    the scope includes the loaders layer
    the scope includes the transformers layer
    the scope includes the models layer
    the scope includes the deciders layer
    the scope includes the traders layer
</rules>
<rules layer="data">
    the data layer requires the trader adapter
    the data layer declares the data adapter
    the data adapter accepts trader output
    the data adapter returns data output
    the data adapter isolates data access
    the data layer exports the data adapter
</rules>
<rules layer="loaders">
    the loaders layer requires the data adapter
    the loaders layer declares the loader adapter
    the loader adapter accepts data output
    the loader adapter returns loader output
    the loader adapter isolates ingestion
    the loaders layer exports the loader adapter
</rules>
<rules layer="transformers">
    the transformers layer requires the loader adapter
    the transformers layer declares the transformer adapter
    the transformer adapter accepts loader output
    the transformer adapter returns transformer output
    the transformer adapter isolates representation change
    the transformers layer exports the transformer adapter
</rules>
<rules layer="models">
    the models layer requires the transformer adapter
    the models layer declares the model adapter
    the model adapter accepts transformer output
    the model adapter returns model output
    the model adapter isolates inference
    the models layer exports the model adapter
</rules>
<rules layer="deciders">
    the deciders layer requires the model adapter
    the deciders layer declares the decider adapter
    the decider adapter accepts model output
    the decider adapter returns decider output
    the decider adapter isolates target selection
    the deciders layer exports the decider adapter
</rules>
<rules layer="traders">
    the traders layer requires the decider adapter
    the traders layer declares the trader adapter
    the trader adapter accepts decider output
    the trader adapter returns trader output
    the trader adapter isolates execution
    the traders layer exports the trader adapter
</rules>
<rules layer="testing" defer>
    the testing layer is outside the active scope
    the testing layer verifies type discriminator resolution
    the testing layer verifies generic adapter invariance
</rules>
</rules>
````
